import asyncio

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, VSplit, to_container
from prompt_toolkit.layout.dimension import Dimension

from . import style, widgets

import logging  # isort:skip
_log = logging.getLogger(__name__)


class UI:
    def __init__(self, jobs):
        self._jobs = jobs
        self._jobs_added = []
        self.log = widgets.Log()
        self._app = self._make_app()

    def error(self, exception):
        self.log.error(exception)

    _max_width = 120

    def _make_app(self):
        self._container = HSplit(
            width=Dimension(max=self._max_width),
            children=[],
        )
        layout = Layout(
            HSplit([
                # The VSplit is only needed because max_width is ignored otherwise
                # https://github.com/prompt-toolkit/python-prompt-toolkit/issues/1192
                VSplit([self._container]),
                self.log,
            ])
        )

        kb = KeyBindings()

        @kb.add('escape')
        @kb.add('c-g')
        @kb.add('c-q')
        def _(event, self=self):
            self._cancel_all_jobs(wait=True)

        @kb.add('c-c')
        def _(event, self=self):
            self._cancel_all_jobs(wait=False)
            if self._app.is_running:
                self._app.exit(1)

        app = Application(layout=layout,
                          key_bindings=kb,
                          style=style.style,
                          full_screen=False,
                          erase_when_done=False,
                          mouse_support=False)
        # Make escape key work
        app.timeoutlen = 0.1
        app.ttimeoutlen = 0.1
        return app

    def run(self):
        self._app.create_background_task(self.do_jobs())
        return self._app.run()

    async def do_jobs(self):
        # Create all job widgets first so they can set up callbacks early before
        # they miss any events
        jobws = [widgets.JobWidget(job) for job in self._jobs]

        # Start jobs one by one; wait for interactive jobs to finish
        background_jobs = []
        for jobw in jobws:
            _log.debug('Starting job: %r', jobw.job)
            jobw.job.start()
            _log.debug('Activating job widget: %r', jobw)
            jobw.activate()
            self._jobs_added.append(jobw.job)
            self._container.children.append(to_container(jobw))
            try:
                self._app.layout.focus(jobw)
            except ValueError:
                # Container cannot be focused
                background_jobs.append(jobw.job)
            else:
                _log.debug('Waiting for interactive job to finish: %r', jobw.job.name)
                await jobw.job.wait()
                _log.debug('Interactive job finished: %r', jobw.job.name)

        # Wait for all non-interactive jobs to finish
        for job in background_jobs:
            _log.debug('Waiting for background job to finish: %r', job.name)
            await job.wait()
            _log.debug('Background job finished: %r', job.name)

        # If this coroutine is finished before self._app.run() has set
        # self._app.is_running to True, self._app.exit() is not called and the
        # application never terminates.
        while not self._app.is_running:
            await asyncio.sleep(0)

        # Return last job's exit code
        self._app.exit(jobw.job.exit_code)

    def _cancel_all_jobs(self, wait=True):
        for job in self._jobs_added:
            _log.debug('Finishing job: %r', job)
            job.finish()
            if wait:
                _log.debug('Waiting for job: %r', job)
                self._app.create_background_task(job.wait())
