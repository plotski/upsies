import asyncio

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window, to_container
from prompt_toolkit.layout.dimension import Dimension

from . import style, widgets

import logging  # isort:skip
_log = logging.getLogger(__name__)


class UI:
    def __init__(self, jobs):
        self._jobs = [j for j in jobs if j is not None]
        self._app = self._make_app()
        self._exception = None
        self._loop = asyncio.get_event_loop()
        self._loop.set_exception_handler(self._handle_exception)

    _max_width = 120

    def _make_app(self):
        # Layout does not accept an empty list of children. We add an empty
        # Window that doesn't display anything and remove it once we've added
        # the first real child.
        # https://github.com/prompt-toolkit/python-prompt-toolkit/issues/1257
        self._initial_placeholder = Window()
        self._container = HSplit(
            width=Dimension(max=self._max_width),
            children=[self._initial_placeholder],
        )
        self._layout = Layout(self._container)

        kb = KeyBindings()

        @kb.add('escape')
        @kb.add('c-g')
        @kb.add('c-q')
        @kb.add('c-c')
        def _(event, self=self):
            if self._app.is_running:
                self._exit(1)

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

    def _remove_initial_placeholder(self):
        if self._initial_placeholder in self._job_widgets:
            self._job_widgets.remove(self._initial_placeholder)

    def run(self):
        # Add JobWidgets in a background task
        do_jobs_task = self._loop.create_task(self._do_jobs())
        do_jobs_task.add_done_callback(self._exit_on_exception)

        # Block until all jobs are finished. Return value is the value passed to
        # _exit() which must be called when an exception occurs or when all jobs
        # have finished. If _exit() is not called, self._app.run() blocks
        # forever.
        exit_code = self._app.run(set_exception_handler=False)
        _log.debug('TUI terminated with exit_code=%r, task=%r', exit_code, do_jobs_task)

        if self._exception:
            raise self._exception
        else:
            return exit_code

    def _handle_exception(self, loop, context):
        exception = context.get('exception')
        if exception:
            _log.debug('Caught unhandled exception: %r', exception)
            if not self._exception:
                self._exception = exception
            self._exit()

    def _exit_on_exception(self, fut):
        try:
            fut.result()
        except BaseException as e:
            if not self._exception:
                _log.debug('Caught exception from %r: %r', fut, e)
                self._exception = e
            self._exit()

    def _exit_on_error(self, job):
        if job.exit_code != 0:
            _log.debug('Exit code from %s: %r', job.name, job.exit_code)
            self._exit(job.exit_code)

    def _exit(self, exit_code=None):
        self._finish_jobs()
        if self._app.is_running and not self._app.is_done:
            if exit_code is None:
                self._app.exit()
            else:
                self._app.exit(exit_code)

    def _finish_jobs(self):
        for job in self._jobs:
            if not job.is_finished:
                job.finish()

    @property
    def _job_widgets(self):
        return self._container.children

    async def _do_jobs(self):
        # First, create widgets so they can callbacks can be registered before
        # any events are fired.
        jobws = [widgets.JobWidget(j) for j in self._jobs]

        # Start all jobs. Interactive jobs and jobs that need output from other
        # jobs will block when their wait() is called.
        for job in self._jobs:
            if job.autostart:
                job.start()

        # Separate interactive jobs from non-interactive jobs.
        background_jobws = [jw for jw in jobws if not jw.is_interactive]
        interactive_jobws = [jw for jw in jobws if jw.is_interactive]

        # Display all background jobs.
        for jobw in background_jobws:
            self._job_widgets.append(to_container(jobw))
            self._remove_initial_placeholder()

        # If any job raises an exception, cancel all jobs.
        for job in self._jobs:
            task = self._loop.create_task(job.wait())
            task.add_done_callback(self._exit_on_exception)
            task.add_done_callback(lambda fut, job=job: self._exit_on_error(job))

        # Prepend interactive jobs. We want them at the top to avoid interactive
        # jobs being jerked around by expanding and shrinking background jobs.
        for index, jobw in enumerate(interactive_jobws):
            self._job_widgets.insert(index, to_container(jobw))
            self._remove_initial_placeholder()
            self._layout.focus(jobw.runtime_widget)
            # Wait for each interactive job to finish before displaying the next.
            await jobw.job.wait()

        # Wait for all jobs to finish. Interactive jobs are already finished,
        # but we need the exit code from the final job, which may or may not be
        # interactive.
        exit_code = 0
        for job in self._jobs:
            await job.wait()
            exit_code = job.exit_code

        # If self._jobs is empty, this coroutine can finish before
        # self._app.run() has fully set its internal state.
        while not self._app.is_running:
            await asyncio.sleep(0)

        # Return last job's exit code
        self._exit(exit_code)
