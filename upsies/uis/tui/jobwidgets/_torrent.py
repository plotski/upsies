from prompt_toolkit.application import get_app

from ....utils import cache, fs
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class CreateTorrentJobWidget(JobWidgetBase):
    def setup(self):
        self._progress = widgets.ProgressBar()
        self.job.on_progress_update(self.handle_progress_update)
        self.job.on_finished(lambda _: get_app().invalidate())

    def activate(self):
        pass

    def handle_progress_update(self, percent_done):
        self._progress.percent = percent_done
        get_app().invalidate()

    @cache.property
    def runtime_widget(self):
        return self._progress


class AddTorrentJobWidget(JobWidgetBase):
    def setup(self):
        self._status = widgets.TextField()
        self.job.on_adding(self.handle_adding_torrent)
        self.job.on_finished(self.handle_finished)

    def activate(self):
        pass

    def handle_adding_torrent(self, torrent_path):
        self._status.text = f'Adding {fs.basename(torrent_path)}...'
        get_app().invalidate()

    def handle_finished(self, _):
        self._status.text = 'Done.'
        get_app().invalidate()

    @cache.property
    def runtime_widget(self):
        return self._status


class CopyTorrentJobWidget(JobWidgetBase):
    def setup(self):
        self._status = widgets.TextField()
        self.job.on_copying(self.handle_copying_torrent)
        self.job.on_finished(self.handle_finished)

    def activate(self):
        pass

    def handle_copying_torrent(self, file_path):
        self._status.text = f'Copying {fs.basename(file_path)}...'
        get_app().invalidate()

    def handle_finished(self, _):
        self._status.text = 'Done.'
        get_app().invalidate()

    @cache.property
    def runtime_widget(self):
        return self._status
