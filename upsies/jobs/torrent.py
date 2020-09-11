import asyncio
import os
import shutil

from .. import errors
from ..tools import client, torrent
from ..utils import fs
from . import _base, _common

import logging  # isort:skip
_log = logging.getLogger(__name__)


class CreateTorrentJob(_base.JobBase):
    name = 'torrent'
    label = 'Torrent'

    def initialize(self, *, content_path, announce_url, trackername,
                   exclude_regexs=(), source=None,
                   add_to=None, copy_to=None):
        self._content_path = content_path
        self._announce_url = announce_url
        self._exclude_regexs = exclude_regexs
        self._source = source
        self._torrent_path = os.path.join(
            self.homedir,
            f'{os.path.basename(content_path)}.{trackername.lower()}.torrent',
        )
        if add_to is not None:
            assert isinstance(add_to, client.ClientApiBase)
        self._client = add_to
        self._destination_path = str(copy_to) if copy_to else None
        self._progress_update_callbacks = []
        self._error_callbacks = []
        self._finished_callbacks = []
        self._file_tree = ''

    def execute(self):
        self._torrent_process = _common.DaemonProcess(
            name=self.name,
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
            finished_callback=self.handle_torrent_created,
        )
        self._torrent_process.start()

    def on_finished(self, callback):
        self._finished_callbacks.append(callback)

    def finish(self):
        if hasattr(self, '_torrent_process'):
            self._torrent_process.stop()
        super().finish()
        for cb in self._finished_callbacks:
            cb(self._output[0] if self._output else None)

    async def wait(self):
        if hasattr(self, '_torrent_process'):
            await self._torrent_process.join()
        if hasattr(self, '_handle_torrent_task'):
            await self._handle_torrent_task
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

    def on_error(self, callback):
        self._error_callbacks.append(callback)

    def handle_error(self, error):
        self.error(error, if_not_finished=True)
        for cb in self._error_callbacks:
            cb(error)

    def handle_torrent_created(self, torrent_path=None):
        _log.debug('Torrent created: %r', torrent_path)
        if torrent_path is None:
            self.finish()
        else:
            tasks = []
            if self.is_adding_torrent:
                tasks.append(asyncio.ensure_future(
                    self._add_torrent(
                        torrent_path=torrent_path,
                        download_path=os.path.dirname(self._content_path),
                        client=self._client,
                    )
                ))
            if self.is_copying_torrent:
                tasks.append(asyncio.ensure_future(
                    self._copy_torrent(
                        torrent_path=torrent_path,
                        destination_path=self._destination_path,
                    )
                ))

            if not tasks:
                self.send(torrent_path, if_not_finished=True)
                self.finish()
            else:
                self._handle_torrent_task = asyncio.ensure_future(
                    asyncio.gather(*tasks)
                )
                self._handle_torrent_task.add_done_callback(lambda fut: self.finish())

    @property
    def is_adding_torrent(self):
        """Whether the created torrent will be added to a BitTorrent client"""
        return bool(self._client)

    async def _add_torrent(self, torrent_path, download_path, client):
        _log.debug('Adding torrent to %s', client.name)
        try:
            await client.add_torrent(
                torrent_path=torrent_path,
                download_path=download_path,
            )
        except errors.RequestError as e:
            self.handle_error(f'Failed to add {os.path.basename(self._torrent_path)} '
                              f'to {self._client.name}: {e}')
        else:
            _log.debug('Added torrent to %s', client.name)
        finally:
            self.send(torrent_path, if_not_finished=True)

    @property
    def is_copying_torrent(self):
        """Whether the created torrent will be copied somewhere"""
        return bool(self._destination_path)

    async def _copy_torrent(self, torrent_path, destination_path):
        _log.debug('Copying %s to %s', torrent_path, destination_path)
        try:
            new_path = shutil.copy2(torrent_path, destination_path)
        except OSError as e:
            if e.strerror:
                msg = e.strerror
            else:
                msg = str(e)
            self.handle_error(f'Failed to copy {os.path.basename(torrent_path)} '
                              f'to {destination_path}: {msg}')
            # Default to original torrent path
            self.send(torrent_path, if_not_finished=True)
        else:
            _log.debug('New torrent path: %s', new_path)
            self.send(new_path, if_not_finished=True)


def _torrent_process(output_queue, input_queue, *args, **kwargs):
    def init_callback(file_tree):
        output_queue.put((_common.DaemonProcess.INIT, file_tree))

    def progress_callback(progress):
        output_queue.put((_common.DaemonProcess.INFO, progress))

    kwargs['init_callback'] = init_callback
    kwargs['progress_callback'] = progress_callback

    try:
        torrent_path = torrent.create(*args, **kwargs)
    except errors.TorrentError as e:
        output_queue.put((_common.DaemonProcess.ERROR, str(e)))
    else:
        output_queue.put((_common.DaemonProcess.RESULT, torrent_path))
