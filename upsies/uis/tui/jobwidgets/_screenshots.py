from prompt_toolkit.application import get_app
from prompt_toolkit.layout.containers import HSplit

from ....utils import cache
from .. import widgets
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ScreenshotsJobWidget(_base.JobWidgetBase):
    def setup(self):
        self._screenshot_progress = widgets.ProgressBar()
        self.job.on_screenshot_path(self.handle_screenshot_path)
        self.job.on_screenshots_finished(lambda _: get_app().invalidate())
        if self.job.is_uploading:
            self._upload_progress = widgets.ProgressBar()
            self.job.on_upload_url(self.handle_screenshot_url)
            self.job.on_uploads_finished(lambda _: get_app().invalidate())

    def activate(self):
        pass

    def handle_screenshot_path(self, path):
        self._screenshot_progress.percent = self.job.screenshots_created / self.job.screenshots_wanted * 100
        get_app().invalidate()

    def handle_screenshot_url(self, url):
        self._upload_progress.percent = self.job.screenshots_uploaded / self.job.screenshots_wanted * 100
        get_app().invalidate()

    @cache.property
    def runtime_widget(self):
        if self.job.is_uploading:
            return HSplit([self._screenshot_progress, self._upload_progress])
        else:
            return self._screenshot_progress
