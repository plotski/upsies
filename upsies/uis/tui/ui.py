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

from . import jobwidgets, style

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
        self._app_terminated = False
        self._exception = None
        self._loop = asyncio.get_event_loop()
        self._loop.set_exception_handler(self._handle_exception)

    def _handle_exception(self, loop, context):
        exception = context.get('exception')
        if exception:
            _log.debug('Caught unhandled exception: %r', exception)
            if not self._exception:
                self._exception = exception
            self._exit()

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
            if job.name in self._jobs:
                raise RuntimeError(f'Job {job.name} was already added')
            else:
                self._jobs[job.name].job = job
                self._jobs[job.name].widget = jobwidgets.JobWidget(job, self._app)
                self._jobs[job.name].container = to_container(self._jobs[job.name].widget)

                # Terminate application if all jobs finished
                job.signal.register('finished', self._exit_if_all_jobs_finished)

                # Terminate application if any job finished with non-zero exit code
                job.signal.register('finished', self._exit_if_job_failed)

                if self._jobs[job.name].widget.is_interactive:
                    # Display next interactive job when currently focused job finishes
                    job.signal.register('finished', self._update_jobs_container)

        self._update_jobs_container()

    def _update_jobs_container(self, *_):
        if self._app_terminated:
            return

        job_containers = []

        # Ensure enabled jobs are started
        for jobinfo in self._enabled_jobs:
            if not jobinfo.job.is_started and jobinfo.job.autostart:
                jobinfo.job.start()

        # List interactive jobs first
        for jobinfo in self._enabled_jobs:
            if jobinfo.widget.is_interactive:
                job_containers.append(jobinfo.container)
                # Focus the first unfinished job
                if not jobinfo.job.is_finished:
                    _log.debug('Active job: %r', jobinfo.job.name)
                    try:
                        self._layout.focus(jobinfo.container)
                    except ValueError:
                        pass
                    break

        # Add non-interactive jobs below interactive jobs so the interactive
        # widgets don't change position when non-interactive widgets change
        # size.
        for jobinfo in self._enabled_jobs:
            if not jobinfo.widget.is_interactive:
                job_containers.append(jobinfo.container)

        # Replace visible containers
        self._jobs_container.children[:] = job_containers

    @property
    def _enabled_jobs(self):
        return tuple(jobinfo for jobinfo in self._jobs.values()
                     if jobinfo.job.is_enabled)

    def run(self, jobs):
        """
        Block while running `jobs`

        :param jobs: Iterable of :class:`~.jobs.base.JobBase` instances

        :raise: Any exception that occured while running jobs

        :return: :attr:`~.JobBase.exit_code` from the first failed job or 0 for
            success
        """
        self.add_jobs(*jobs)

        # Block until _exit() is called
        self._app.run(set_exception_handler=False)

        if self._exception:
            _log.debug('Application exception: %r', self._exception)
            raise self._exception
        else:
            # First non-zero exit_code is the application exit_code
            for jobinfo in self._enabled_jobs:
                _log.debug('Checking exit_code of %r: %r', jobinfo.job.name, jobinfo.job.exit_code)
                if jobinfo.job.exit_code != 0:
                    return jobinfo.job.exit_code
            return 0

    def _exit_if_all_jobs_finished(self, *_):
        if all(jobinfo.job.is_finished for jobinfo in self._enabled_jobs):
            _log.debug('All jobs finished')
            self._exit()

    def _exit_if_job_failed(self, job):
        if not self._app_terminated and job.is_finished and job.exit_code != 0:
            self._exit()
            _log.debug('Terminating application because of failed job: %r', job.name)
            if not self._exception and job.exceptions:
                _log.debug('Exceptions: %r', job.exceptions)
                self._exception = job.exceptions[0]

    def _exit(self):
        if not self._app_terminated:
            if not self._app.is_running and not self._app.is_done:
                self._loop.call_soon(self._exit)
            elif self._app.is_running and not self._app.is_done:
                self._app_terminated = True
                self._finish_jobs()
                self._app.exit()

    def _finish_jobs(self):
        for jobinfo in self._jobs.values():
            if not jobinfo.job.is_finished:
                _log.debug('Finishing %s', jobinfo.job.name)
                jobinfo.job.finish()
