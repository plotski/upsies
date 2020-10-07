from prompt_toolkit.application import get_app

from ....utils import cache
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ScreenshotsJobWidget(JobWidgetBase):
    def setup(self):
        self._screenshot_progress = widgets.ProgressBar()
        self.job.on_output(self.handle_screenshot_path)
        self.job.on_finished(lambda _: get_app().invalidate())

    def activate(self):
        pass

    def handle_screenshot_path(self, path):
        self._screenshot_progress.percent = self.job.screenshots_created / self.job.screenshots_total * 100
        get_app().invalidate()

    @cache.property
    def runtime_widget(self):
        return self._screenshot_progress
