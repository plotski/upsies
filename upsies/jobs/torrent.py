import asyncio
import os

from .. import errors
from ..tools import torrent
from ..tools.btclient import ClientApiBase
from ..utils import daemon, fs
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class CreateTorrentJob(JobBase):
    name = 'create-torrent'
    label = 'Create Torrent'

    def initialize(self, *, content_path, tracker_name, tracker_config):
        self._content_path = content_path
        self._torrent_path = os.path.join(
            self.homedir,
            f'{fs.basename(content_path)}.{tracker_name.lower()}.torrent',
        )
        self._progress_update_callbacks = []
        self._file_tree = ''
        self._torrent_process = daemon.DaemonProcess(
            name=self.name,
            target=_torrent_process,
            kwargs={
                'content_path' : self._content_path,
                'torrent_path' : self._torrent_path,
                'overwrite'    : self.ignore_cache,
                'announce'     : tracker_config['announce'],
                'source'       : tracker_config['source'],
                'exclude'      : tracker_config['exclude'],
            },
            init_callback=self.handle_file_tree,
            info_callback=self.handle_progress_update,
            error_callback=self.error,
            finished_callback=self.handle_torrent_created,
        )

    def execute(self):
        self._torrent_process.start()

    def finish(self):
        self._torrent_process.stop()

    async def wait(self):
        await self._torrent_process.join()
        if not self.is_finished:
            super().finish()
        await super().wait()

    def handle_file_tree(self, file_tree):
        self._file_tree = fs.file_tree(file_tree)

    @property
    def info(self):
        return self._file_tree

    def on_progress_update(self, callback):
        self._progress_update_callbacks.append(callback)

    def handle_progress_update(self, percent_done):
        for cb in self._progress_update_callbacks:
            cb(percent_done)

    def handle_torrent_created(self, torrent_path=None):
        _log.debug('Torrent created: %r', torrent_path)
        if torrent_path:
            self.send(torrent_path, if_not_finished=True)


def _torrent_process(output_queue, input_queue, *args, **kwargs):
    def init_callback(file_tree):
        output_queue.put((daemon.DaemonProcess.INIT, file_tree))

    def progress_callback(progress):
        output_queue.put((daemon.DaemonProcess.INFO, progress))

    kwargs['init_callback'] = init_callback
    kwargs['progress_callback'] = progress_callback

    try:
        torrent_path = torrent.create(*args, **kwargs)
    except errors.TorrentError as e:
        output_queue.put((daemon.DaemonProcess.ERROR, str(e)))
    else:
        output_queue.put((daemon.DaemonProcess.RESULT, torrent_path))


class AddTorrentJob(JobBase):
    name = 'add-torrent'
    label = 'Add Torrent'

    @property
    def cache_file(self):
        return None

    def initialize(self, *, client, download_path=None, torrents=()):
        assert isinstance(client, ClientApiBase)
        self._client = client
        self._download_path = download_path
        self._add_task = None
        self._adding_callbacks = []
        self._added_callbacks = []
        self._torrent_path_queue = asyncio.Queue()
        if torrents:
            for t in torrents:
                self.add(t)
            self.pipe_closed()
        self._add_torrents_task = asyncio.ensure_future(self._add_torrents())

    def execute(self):
        pass

    def finish(self):
        self._torrent_path_queue.put_nowait((None, None))

    async def wait(self):
        await self._add_torrents_task
        super().finish()
        await super().wait()

    def pipe_input(self, torrent_path):
        self.add(torrent_path)

    def pipe_closed(self):
        self._torrent_path_queue.put_nowait((None, None))

    def on_adding(self, callback):
        assert callable(callback)
        self._adding_callbacks.append(callback)

    def on_added(self, callback):
        assert callable(callback)
        self._added_callbacks.append(callback)

    def add(self, torrent_path, download_path=None):
        self._torrent_path_queue.put_nowait((
            torrent_path,
            download_path or self._download_path,
        ))

    MAX_TORRENT_SIZE = 10 * 2**20

    async def add_async(self, torrent_path, download_path=None):
        _log.debug('Adding %s to %s', torrent_path, self._client.name)
        for cb in self._adding_callbacks:
            cb(torrent_path)

        if os.path.exists(torrent_path) and os.path.getsize(torrent_path) > self.MAX_TORRENT_SIZE:
            self.error(f'{torrent_path}: File is too large')
            return

        try:
            torrent_id = await self._client.add_torrent(
                torrent_path=torrent_path,
                download_path=download_path or self._download_path,
            )
        except errors.TorrentError as e:
            self.error(f'Failed to add {fs.basename(torrent_path)} '
                       f'to {self._client.name}: {e}')
        else:
            self.send(torrent_id)
            for cb in self._added_callbacks:
                cb(torrent_id)

    async def _add_torrents(self):
        while True:
            try:
                torrent_path, download_path = await asyncio.wait_for(
                    self._torrent_path_queue.get(),
                    timeout=0.1,
                )
            except asyncio.TimeoutError:
                pass
            else:
                if torrent_path is None:
                    break
                else:
                    await self.add_async(torrent_path, download_path)


class CopyTorrentJob(JobBase):
    name = 'copy-torrent'
    label = 'Copy Torrent'

    @property
    def cache_file(self):
        return None

    def initialize(self, *, destination, files=()):
        self._destination = destination
        self._copying_callbacks = []
        self._copied_callbacks = []
        if files:
            for f in files:
                self.copy(f)
            self.pipe_closed()

    def execute(self):
        pass

    def pipe_input(self, file_path):
        self.copy(file_path)

    def pipe_closed(self):
        self.finish()

    def on_copying(self, callback):
        assert callable(callback)
        self._copying_callbacks.append(callback)

    def on_copied(self, callback):
        assert callable(callback)
        self._copied_callbacks.append(callback)

    MAX_FILE_SIZE = 10 * 2**20

    def copy(self, file_path, destination=None):
        dest = destination or self._destination
        _log.debug('Copying %s to %s', file_path, dest)

        if os.path.exists(file_path) and os.path.getsize(file_path) > self.MAX_FILE_SIZE:
            self.error(f'{file_path}: File is too large')
            return

        import shutil
        try:
            new_path = shutil.copy2(file_path, dest)
        except OSError as e:
            if e.strerror:
                msg = e.strerror
            else:
                msg = str(e)
            self.error(f'Failed to copy {fs.basename(file_path)} '
                       f'to {dest}: {msg}')
            # Default to original torrent path
            self.send(file_path, if_not_finished=True)
        else:
            self.send(new_path, if_not_finished=True)
