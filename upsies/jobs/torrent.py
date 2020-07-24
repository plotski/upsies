import os

from .. import errors
from ..tools import torrent
from ..utils import fs
from . import _base, _common

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Torrent(_base.JobBase):
    name = 'torrent'
    label = 'Torrent'

    def initialize(self, *, content_path, announce_url, trackername,
                   exclude_regexs=(), source=None):
        self._content_path = content_path
        self._announce_url = announce_url
        self._exclude_regexs = exclude_regexs
        self._source = source
        self._torrent_path = os.path.join(
            self.homedir,
            f'{os.path.basename(content_path)}.{trackername}.torrent',
        )
        self._progress_update_callbacks = []
        self._error_callbacks = []
        self._finished_callbacks = []
        self._file_tree = ''

    def execute(self):
        self._torrent_process = _common.DaemonProcess(
            target=_torrent_process,
            kwargs={
                'content_path'   : self._content_path,
                'torrent_path'   : self._torrent_path,
                'announce_url'   : self._announce_url,
                'source'         : self._source,
                'exclude_regexs' : self._exclude_regexs,
            },
            init_callback=self.handle_file_tree,
            info_callback=self.handle_progress_update,
            error_callback=self.handle_error,
            finished_callback=self.handle_finished,
        )
        self._torrent_process.start()

    def finish(self):
        if hasattr(self, '_torrent_process'):
            self._torrent_process.stop()
        super().finish()

    async def wait(self):
        if hasattr(self, '_torrent_process'):
            await self._torrent_process.join()
        await super().wait()

    def on_progress_update(self, callback):
        self._progress_update_callbacks.append(callback)

    def handle_progress_update(self, percent_done):
        for cb in self._progress_update_callbacks:
            cb(percent_done)

    def on_error(self, callback):
        self._error_callbacks.append(callback)

    def handle_error(self, error):
        self.error(error, if_not_finished=True)
        for cb in self._error_callbacks:
            cb(error)

    def on_finished(self, callback):
        self._finished_callbacks.append(callback)

    def handle_finished(self, torrent_path=None):
        if torrent_path is not None:
            self.send(torrent_path, if_not_finished=True)
        for cb in self._finished_callbacks:
            cb(torrent_path)
        self.finish()

    def handle_file_tree(self, file_tree):
        self._file_tree = fs.file_tree(file_tree)

    @property
    def info(self):
        return self._file_tree


def _torrent_process(output_queue, input_queue, *args, **kwargs):
    def init_callback(file_tree):
        output_queue.put_nowait((_common.DaemonProcess.INIT, file_tree))

    def progress_callback(progress):
        output_queue.put_nowait((_common.DaemonProcess.INFO, progress))

    kwargs['init_callback'] = init_callback
    kwargs['progress_callback'] = progress_callback

    try:
        torrent_path = torrent.create(*args, **kwargs)
    except errors.TorrentError as e:
        output_queue.put_nowait((_common.DaemonProcess.ERROR, str(e)))
    else:
        output_queue.put_nowait((_common.DaemonProcess.RESULT, torrent_path))
