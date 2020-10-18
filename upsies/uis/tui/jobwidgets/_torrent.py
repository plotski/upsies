from ....utils import cache, fs
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class CreateTorrentJobWidget(JobWidgetBase):
    def setup(self):
        self._progress = widgets.ProgressBar()
        self.job.on_progress_update(self.handle_progress_update)
        self.job.on_finished(lambda _: self.invalidate())

    def handle_progress_update(self, percent_done):
        self._progress.percent = percent_done
        self.invalidate()

    @cache.property
    def runtime_widget(self):
        return self._progress


class AddTorrentJobWidget(JobWidgetBase):
    def setup(self):
        self._status = widgets.TextField()
        self.job.on_adding(self.handle_adding_torrent)
        self.job.on_finished(self.handle_finished)

    def handle_adding_torrent(self, torrent_path):
        self._status.text = f'Adding {fs.basename(torrent_path)}...'
        self.invalidate()

    def handle_finished(self, _):
        self._status.text = 'Done.'
        self.invalidate()

    @cache.property
    def runtime_widget(self):
        return self._status


class CopyTorrentJobWidget(JobWidgetBase):
    def setup(self):
        self._status = widgets.TextField()
        self.job.on_copying(self.handle_copying_torrent)
        self.job.on_finished(self.handle_finished)

    def handle_copying_torrent(self, file_path):
        self._status.text = f'Copying {fs.basename(file_path)}...'
        self.invalidate()

    def handle_finished(self, _):
        self._status.text = 'Done.'
        self.invalidate()

    @cache.property
    def runtime_widget(self):
        return self._status
