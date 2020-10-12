import asyncio

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window, to_container
from prompt_toolkit.layout.dimension import Dimension

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
        self._exception = None

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
            self._cancel_jobs(wait=True)
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

    def _exit(self, exit_code):
        if not self._app.is_done:
            self._app.exit(exit_code)

    def run(self):
        task = self._app.create_background_task(self._do_jobs())
        task.add_done_callback(self._jobs_done)
        exit_code = self._app.run(set_exception_handler=False)
        if self._exception:
            raise self._exception
        else:
            return exit_code

    def _jobs_done(self, fut):
        try:
            fut.result()
        except Exception as e:
            self._exception = e
            self._exit(1)

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

        # Wait for all jobs to finish. Interactive jobs are already finished,
        # but we want an exit code from the final job and there may be no
        # background jobs.
        exit_code = 0
        for job in self._jobs:
            if not job.is_finished:
                _log.debug('Waiting for background job to finish: %r', job.name)
                await job.wait()
            exit_code = job.exit_code

        # If this coroutine is finished before self._app.run() has set
        # self._app.is_running to True, self._app.exit() is not called and the
        # application never terminates.
        while not self._app.is_running:
            await asyncio.sleep(0)

        # Return last job's exit code
        self._exit(exit_code)

    def _cancel_jobs(self, wait=True):
        self._cancelled = False
        _log.debug('Cancelling %s jobs', len(self._jobs))
        for job in self._jobs:
            if not job.is_finished:
                job.finish()

        if wait:
            for job in self._jobs:
                if not job.is_finished:
                    _log.debug('Waiting for job: %r', job)
                    self._app.create_background_task(job.wait())
