import asyncio

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window, to_container
from prompt_toolkit.layout.dimension import Dimension

from ... import errors
from ...jobs import JobBase
from . import style, widgets

import logging  # isort:skip
_log = logging.getLogger(__name__)


class UI:
    def __init__(self, jobs):
        self._jobs = [j for j in jobs if j is not None]
        for j in self._jobs:
            assert isinstance(j, JobBase), j
        self._app = self._make_app()

    @property
    def _job_widgets(self):
        return self._container.children

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

        app = Application(layout=self._layout,
                          key_bindings=kb,
                          style=style.style,
                          full_screen=False,
                          erase_when_done=False,
                          mouse_support=False)
        # Make escape key work
        app.timeoutlen = 0.1
        app.ttimeoutlen = 0.1
        return app

    def _remove_initial_placeholder(self):
        if self._initial_placeholder in self._job_widgets:
            self._job_widgets.remove(self._initial_placeholder)

    def run(self):
        # Add JobWidgets in a background task
        do_jobs_task = asyncio.get_event_loop().create_task(self._do_jobs())
        do_jobs_task.add_done_callback(self._exit_on_exception)

        # Block until all jobs are finished.
        # Return value is the exit_code property of the final job.
        exit_code = self._app.run()
        _log.debug('TUI terminated with exit_code=%r, task=%r', exit_code, do_jobs_task)

        # Make sure _do_jobs() is done
        if not do_jobs_task.done():
            do_jobs_task.cancel()
            try:
                asyncio.get_event_loop().run_until_complete(do_jobs_task)
            except BaseException:
                pass

        # Raise any exception except for CancelledError
        try:
            do_jobs_task.result()
        except asyncio.CancelledError:
            raise errors.CancelledError()
        else:
            return exit_code

    def _exit_on_exception(self, task):
        try:
            task.result()
        except BaseException:
            self._exit()

    def _exit(self, exit_code=None):
        self._finish_jobs()
        if not self._app.is_done:
            if exit_code is None:
                self._app.exit()
            else:
                self._app.exit(exit_code)

    def _finish_jobs(self):
        for job in self._jobs:
            if not job.is_finished:
                job.finish()

    async def _do_jobs(self):
        # First create widgets so they can register their callbacks with their
        # jobs before they miss any events
        jobws = [widgets.JobWidget(j) for j in self._jobs]

        # Start all jobs
        for job in self._jobs:
            job.start()

        # Separate interactive jobs from non-interactive jobs
        background_jobws = [jw for jw in jobws if not jw.is_interactive]
        interactive_jobws = [jw for jw in jobws if jw.is_interactive]

        # Display all background jobs
        for jobw in background_jobws:
            self._job_widgets.append(to_container(jobw))
            self._remove_initial_placeholder()

        # Prepend interactive jobs one by one. We want them at the top to avoid
        # interactive jobs being moved by expanding and shrinking background
        # jobs.
        for index, jobw in enumerate(interactive_jobws):
            self._job_widgets.insert(index, to_container(jobw))
            self._remove_initial_placeholder()
            self._layout.focus(jobw.runtime_widget)
            _log.debug('Waiting for interactive job to finish: %r', jobw.job.name)
            await jobw.job.wait()

        # Wait for all jobs to finish and get exceptions from job.wait().
        # Interactive jobs are already finished, but we want an exit code from
        # the final job and there may be no background jobs.
        exit_code = 0
        for job in self._jobs:
            await job.wait()
            exit_code = job.exit_code

        # If self._jobs is empty, this coroutine can finish before
        # self._app.run() has fully set its internal state. As a result,
        # self._exit() can call self._app.exit() multiple times (which raises
        # RuntimeError) or not at all, leaving the application running until
        # ctrl-c is pressed.
        while not self._app.is_running:
            await asyncio.sleep(0)

        # Return last job's exit code
        self._exit(exit_code)
