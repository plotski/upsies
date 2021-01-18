"""
Main UI widget and job manager
"""

import asyncio
import collections
import types

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window, to_container

from . import style, widgets

import logging  # isort:skip
_log = logging.getLogger(__name__)


class UI:
    def __init__(self):
        # Map JobBase.name to SimpleNamespace with attributes:
        #   job       - JobBase instance
        #   widget    - JobWidgetBase instance
        #   container - Container instance
        self._jobs = collections.defaultdict(lambda: types.SimpleNamespace())
        self._app = self._make_app()
        self._exception = None
        self._wait_for_all_jobs_task = None
        self._loop = asyncio.get_event_loop()
        self._loop.set_exception_handler(self._handle_exception)

    def _make_app(self):
        self._jobs_container = HSplit(
            # FIXME: Layout does not accept an empty list of children. We add an
            #        empty Window that doesn't display anything that gets
            #        removed automatically when we rebuild
            #        self._jobs_container.children.
            #        https://github.com/prompt-toolkit/python-prompt-toolkit/issues/1257
            children=[Window()],
            style='class:default',
        )
        self._layout = Layout(self._jobs_container)

        kb = KeyBindings()

        @kb.add('escape')
        @kb.add('c-g')
        @kb.add('c-q')
        @kb.add('c-c')
        def _(event, self=self):
            if self._app.is_running:
                self._exit()

        app = Application(
            layout=self._layout,
            key_bindings=kb,
            style=style.style,
            full_screen=False,
            erase_when_done=False,
            mouse_support=False,
        )
        # Make escape key work
        app.timeoutlen = 0.1
        app.ttimeoutlen = 0.1
        return app

    def add_jobs(self, *jobs):
        """Add :class:`~.jobs.base.JobBase` instances"""
        for job in jobs:
            if job.name not in self._jobs:
                self._jobs[job.name].job = job
                self._jobs[job.name].widget = widgets.JobWidget(job)
                self._jobs[job.name].container = to_container(self._jobs[job.name].widget)
                _log.debug('Created JobWidget %r: %r', job.name, self._jobs[job.name])

                # Terminate application if job encounters error
                job.signal.register('error', self._exit)

                if self._jobs[job.name].widget.is_interactive:
                    # Display next interactive job
                    job.signal.register('finished', self._update_jobs_container)

                if job.autostart:
                    job.start()

        self._update_jobs_container()

    def _update_jobs_container(self):
        job_containers = []

        # Show all finished interactive jobs and the first unfinished
        # interactive job
        for jobinfo in self._jobs.values():
            if jobinfo.widget.is_interactive:
                job_containers.append(jobinfo.container)
                # Focus the first unfinished job and stop adding more
                if not jobinfo.job.is_finished:
                    _log.debug('Active job: %r', jobinfo.job.name)
                    self._layout.focus(jobinfo.container)
                    break

        # Add non-interactive jobs below interactive jobs so the interactive
        # widgets don't change position while non-interactive widgets change
        # size.
        for jobinfo in self._jobs.values():
            if not jobinfo.widget.is_interactive:
                job_containers.append(jobinfo.container)

        # Replace visible containers
        self._jobs_container.children[:] = job_containers

    def run(self, jobs):
        """
        Block while running `jobs`

        :param jobs: Iterable of :class:`~.jobs.base.JobBase` instances

        :raise: Any exception that occured while running jobs

        :return: Application exit code: 0 for success, anything else for failure
        """
        self.add_jobs(*jobs)

        self._wait_for_all_jobs_task = self._loop.create_task(self._wait_for_all_jobs())
        self._wait_for_all_jobs_task.add_done_callback(self._exit_on_exception)

        # Block until all jobs are finished
        try:
            self._app.run(set_exception_handler=False)
        finally:
            self._finish_jobs()
            try:
                asyncio.get_event_loop().run_until_complete(self._wait_for_all_jobs_task)
            except asyncio.CancelledError:
                pass

        if self._exception:
            raise self._exception
        else:
            # First non-zero exit_code is the applications exit_code
            for jobinfo in self._jobs.values():
                _log.debug('Checking exit_code of %r: %r', jobinfo.job.name, jobinfo.job.exit_code)
                if not isinstance(jobinfo.job.exit_code, int):
                    raise TypeError('Job has invalid exit_code: {jobinfo.job.exit_code!r}')
                elif jobinfo.job.exit_code != 0:
                    return jobinfo.job.exit_code
            return 0

    async def _wait_for_all_jobs(self):
        # FIXME: This coroutine can finish before self._app has found its
        #        internal state. self._exit() can find self._app.is_running to
        #        be False and not call self._app.exit(). self._app then becomes
        #        fully alive and blocks until self._app.exit() is called, which
        #        never happens because self._exit() was already called.
        while not self._app.is_running:
            _log.debug('Waiting for %r to be running', self._app)
            await asyncio.sleep(0)

        # Wait for all jobs simultaneously so that the first exception raised by
        # any job.wait() is raised here. We don't need to catch it because
        # _handle_exception() will take care of it.
        await asyncio.gather(*(jobinfo.job.wait() for jobinfo in self._jobs.values()))

        _log.debug('All jobs terminated')
        self._exit()

    def _handle_exception(self, loop, context):
        exception = context.get('exception')
        if exception:
            _log.debug('Caught unhandled exception: %r', exception)
            if not self._exception:
                self._exception = exception
            if self._wait_for_all_jobs_task:
                self._wait_for_all_jobs_task.cancel()
            self._exit()

    def _exit_on_exception(self, fut):
        try:
            fut.result()
        except asyncio.CancelledError:
             pass
        except BaseException as e:
            if not self._exception:
                _log.debug('Caught exception from %r: %r', fut, e)
                self._exception = e
            self._exit()

    def _exit(self, *_, **__):
        if self._app.is_running and not self._app.is_done:
            self._app.exit()

    def _finish_jobs(self):
        for jobinfo in self._jobs.values():
            jobinfo.job.finish()
