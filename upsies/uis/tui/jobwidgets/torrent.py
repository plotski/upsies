from ....utils import cached_property
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class CreateTorrentJobWidget(JobWidgetBase):
    def setup(self):
        self._progress = widgets.ProgressBar()
        self.job.signal.register('progress_update', self.handle_progress_update)
        self.job.signal.register('finished', self.invalidate)

    def handle_progress_update(self, percent_done):
        self._progress.percent = percent_done
        self.invalidate()

    @cached_property
    def runtime_widget(self):
        return self._progress


class AddTorrentJobWidget(JobWidgetBase):
    def setup(self):
        self.job.signal.register('adding', lambda _: self.invalidate())
        self.job.signal.register('added', lambda _: self.invalidate())

    @cached_property
    def runtime_widget(self):
        return None


class CopyTorrentJobWidget(JobWidgetBase):
    def setup(self):
        self.job.signal.register('copying', lambda _: self.invalidate())
        self.job.signal.register('copied', lambda _: self.invalidate())

    @cached_property
    def runtime_widget(self):
        return None
