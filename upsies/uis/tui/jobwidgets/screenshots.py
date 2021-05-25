from ....utils import cached_property, fs
from .. import utils, widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ScreenshotsJobWidget(JobWidgetBase):
    def setup(self):
        content_name = fs.basename(self.job.kwargs['content_path'])
        self._throbber = utils.Throbber(
            format=f'Analyzing {content_name} {{throbber}}',
            callback=self.handle_throbber_state,
            active=True,
        )
        self._screenshot_progress = widgets.ProgressBar()
        self.job.signal.register('output', self.handle_screenshot_path)
        self.job.signal.register('finished', lambda _: self.invalidate())

    def handle_throbber_state(self, state):
        self.job.info = state
        self.invalidate()

    def handle_screenshot_path(self, path):
        self._throbber.active = False
        self.job.info = ''
        if self.job.screenshots_total > 0:
            self._screenshot_progress.percent = self.job.screenshots_created / self.job.screenshots_total * 100
            self.invalidate()

    @cached_property
    def runtime_widget(self):
        return self._screenshot_progress
