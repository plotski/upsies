"""
Create torrent file
"""

import asyncio
import os
import queue

from .. import errors
from ..utils import btclients, daemon, fs, torrent
from . import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class CreateTorrentJob(base.JobBase):
    """
    Create torrent file

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``progress_update``
            Emitted in roughly equal intervals to provide creation progress.
            Registered callbacks get a `float` between 0.0 and 100.0 as a
            positional argument.
    """

    name = 'torrent'
    label = 'Torrent'

    @property
    def cache_id(self):
        """:attr:`.TrackerBase.name`"""
        return self._tracker.name

    def initialize(self, *, tracker, content_path):
        """
        Set internal state

        :param TrackerBase tracker: Return value of :func:`.trackers.tracker`
        :param content_path: Path to file or directory
        """
        self._tracker = tracker
        self._content_path = content_path
        self._torrent_path = os.path.join(
            self.home_directory,
            f'{fs.basename(content_path)}.{tracker.name.lower()}.torrent',
        )
        self.signal.add('progress_update')
        self._file_tree = ''
        self._announce_url_task = None
        self._torrent_process = None

    def execute(self):
        """Get announce URL from `tracker`, then execute torrent creation subprocess"""

        def create_torrent_process_wrapper(task):
            try:
                self._create_torrent_process(task.result())
            except errors.RequestError as e:
                self.error(e)
            except Exception as e:
                self.exception(e)

        self._announce_url_task = asyncio.ensure_future(
            self._tracker.with_login(
                self._tracker.get_announce_url(),
            )
        )
        self._announce_url_task.add_done_callback(create_torrent_process_wrapper)

    def _create_torrent_process(self, announce_url):
        self._torrent_process = daemon.DaemonProcess(
            name=self.name,
            target=_torrent_process,
            kwargs={
                'content_path' : self._content_path,
                'torrent_path' : self._torrent_path,
                'overwrite'    : self.ignore_cache,
                'announce'     : announce_url,
                'source'       : self._tracker.config['source'],
                'exclude'      : self._tracker.config['exclude'],
            },
            init_callback=self._handle_file_tree,
            info_callback=self._handle_progress_update,
            error_callback=self.error,
            finished_callback=self._handle_torrent_created,
        )
        self._torrent_process.start()

    def finish(self):
        """Terminate torrent creation subprocess and finish"""
        if self._torrent_process:
            self._torrent_process.stop()
        if self._announce_url_task:
            self._announce_url_task.cancel()
        super().finish()

    async def wait(self):
        """Join torrent creation subprocess"""
        if self._torrent_process:
            await self._torrent_process.join()
        await super().wait()

    def _handle_file_tree(self, file_tree):
        self._file_tree = fs.file_tree(file_tree)

    @property
    def info(self):
        """File tree as returned by :func:`.fs.file_tree`"""
        return self._file_tree

    def _handle_progress_update(self, percent_done):
        self.signal.emit('progress_update', percent_done)

    def _handle_torrent_created(self, torrent_path=None):
        _log.debug('Torrent created: %r', torrent_path)
        if torrent_path:
            self.send(torrent_path)
        self.finish()


def _torrent_process(output_queue, input_queue, *args, **kwargs):
    def init_callback(file_tree):
        output_queue.put((daemon.MsgType.init, file_tree))

    def progress_callback(progress):
        try:
            typ, msg = input_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if typ == daemon.MsgType.terminate:
                # Any truthy return value cancels torrent.create()
                return 'cancel'

        output_queue.put((daemon.MsgType.info, progress))

    kwargs['init_callback'] = init_callback
    kwargs['progress_callback'] = progress_callback

    try:
        torrent_path = torrent.create(*args, **kwargs)
    except errors.TorrentError as e:
        output_queue.put((daemon.MsgType.error, str(e)))
    else:
        output_queue.put((daemon.MsgType.result, torrent_path))


class AddTorrentJob(base.QueueJobBase):
    """
    Add torrent(s) to a BitTorrent client

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``adding``
            Emitted when attempting to add a torrent. Registered callbacks get
            the path to the torrent file as a positional argument.

        ``added``
            Emitted when the torrent was added successfully. Registered
            callbacks get the added torrent's info hash as a positional
            argument.
    """

    name = 'add-torrent'
    label = 'Add Torrent'
    cache_id = None  # Don't cache output

    def initialize(self, *, client, download_path=None, enqueue=()):
        """
        Set internal state

        :param client: Return value of :func:`.btclients.client`
        :param download_path: Path to the torrent's download location or `None`
            to use the client's default path
        :param enqueue: Sequence of torrent file paths to add

        If `enqueue` is given and not empty, this job is finished as soon as its
        last item is added.
        """
        assert isinstance(client, btclients.ClientApiBase), f'Not a ClientApiBase: {client!r}'
        self._client = client
        self._download_path = download_path
        self.signal.add('adding')
        self.signal.add('added')
        self._info = ''
        self.signal.register('adding', lambda tp: setattr(self, '_info', f'Adding {fs.basename(tp)}'))
        self.signal.register('added', lambda _: setattr(self, '_info', ''))
        self.signal.register('finished', lambda: setattr(self, '_info', ''))
        self.signal.register('error', lambda _: setattr(self, '_info', ''))

    MAX_TORRENT_SIZE = 10 * 2**20  # 10 MiB
    """Upper limit of acceptable size of `.torrent` files"""

    async def handle_input(self, torrent_path):
        _log.debug('Adding %s to %s', torrent_path, self._client.name)
        self.signal.emit('adding', torrent_path)

        if os.path.exists(torrent_path) and os.path.getsize(torrent_path) > self.MAX_TORRENT_SIZE:
            self.error(f'{torrent_path}: File is too large')
            return

        try:
            torrent_hash = await self._client.add_torrent(
                torrent_path=torrent_path,
                download_path=self._download_path,
            )
        except errors.TorrentError as e:
            self.error(f'Failed to add {torrent_path} to {self._client.name}: {e}')
        else:
            self.send(torrent_hash)
            self.signal.emit('added', torrent_hash)

    @property
    def info(self):
        """Current status as user-readable string"""
        return self._info


class CopyTorrentJob(base.QueueJobBase):
    """
    Copy file(s)

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``copying``
            Emitted when attempting to copy a file. Registered callbacks get the
            source file path as a positional argument.

        ``copied``
            Emitted when the copy attempt ended. Registered callbacks get the
            destination file path (success) or the source file path (failure) as
            a positional argument.
    """

    name = 'copy-torrent'
    label = 'Copy Torrent'
    cache_id = None  # Don't cache output

    def initialize(self, *, destination, enqueue=()):
        """
        Set internal state

        :param destination: Where to put the torrent(s)
        :param enqueue: Sequence of file paths to copy

        If `enqueue` is given and not empty, this job is finished as soon as its
        last item is copied.
        """
        self._destination = None if not destination else str(destination)
        self.signal.add('copying')
        self.signal.add('copied')
        self._info = ''
        self.signal.register('copying', lambda fp: setattr(self, '_info', f'Copying {fs.basename(fp)}'))
        self.signal.register('copied', lambda _: setattr(self, '_info', ''))
        self.signal.register('finished', lambda: setattr(self, '_info', ''))
        self.signal.register('error', lambda _: setattr(self, '_info', ''))

    MAX_FILE_SIZE = 10 * 2**20  # 10 MiB
    """Upper limit of acceptable file size"""

    async def handle_input(self, filepath):
        _log.debug('Copying %s to %s', filepath, self._destination)

        if not os.path.exists(filepath):
            self.error(f'{filepath}: No such file')

        elif os.path.getsize(filepath) > self.MAX_FILE_SIZE:
            self.error(f'{filepath}: File is too large')

        else:
            self.signal.emit('copying', filepath)

            import shutil
            try:
                new_path = shutil.copy2(filepath, self._destination)
            except OSError as e:
                if e.strerror:
                    msg = e.strerror
                else:
                    msg = str(e)
                self.error(f'Failed to copy {filepath} to {self._destination}: {msg}')
                # Default to original torrent path
                self.send(filepath)
            else:
                self.send(new_path)
                self.signal.emit('copied', new_path)

    @property
    def info(self):
        """Current status as user-readable string"""
        return self._info
