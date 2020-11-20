import os

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import ConditionalContainer, HSplit

from ....utils import cache
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ScreenshotsJobWidget(JobWidgetBase):
    def setup(self):
        content_name = os.path.basename(self.job.kwargs['content_path'])
        self._status_text = widgets.TextField(f'Analyzing {content_name} ...')
        self._screenshot_progress = widgets.ProgressBar()
        self.job.signal.register('output', self.handle_screenshot_path)
        self.job.signal.register('finished', lambda _: self.invalidate())

    def handle_screenshot_path(self, path):
        if self.job.screenshots_total > 0:
            self._screenshot_progress.percent = self.job.screenshots_created / self.job.screenshots_total * 100
            self.invalidate()

    @cache.property
    def runtime_widget(self):
        return HSplit(
            children=[
                ConditionalContainer(
                    filter=Condition(lambda: not self.job.video_file),
                    content=self._status_text,
                ),
                ConditionalContainer(
                    filter=Condition(lambda: self.job.video_file),
                    content=self._screenshot_progress,
                ),
            ],
        )
