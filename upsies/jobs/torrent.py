"""
Create torrent file
"""

import fnmatch
import os
import queue

from .. import errors
from ..utils import btclients, daemon, fs, is_regex_pattern, torrent
from . import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class CreateTorrentJob(base.JobBase):
    """
    Create torrent file

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``announce_url``
            Emitted before and after successful announce URL retrieval.
            Registered callbacks get an :class:`Ellipsis` to indicate the
            retrieval attempt and the announce URL if the attempt was
            successful.

        ``file_tree``
            Emitted when torrent creation begins. Registered callbacks get
            nested `(file_name, file_size)` tuples (see
            :func:`~.utils.torrent.create`) as a positional argument. (See also
            :func:`.fs.format_file_tree`.)

        ``progress_update``
            Emitted at roughly equal intervals to provide information about the
            torrent creation progress. Registered callbacks get a
            :class:`~.torrent.CreateTorrentProgress` instance as a positional
            argument.
    """

    name = 'torrent'
    label = 'Torrent'
    cache_id = None

    def initialize(self, *, tracker, content_path, exclude_files=(), reuse_torrent_path=None):
        """
        Set internal state

        :param TrackerBase tracker: Return value of :func:`.trackers.tracker`
        :param content_path: Path to file or directory
        :param reuse_torrent_path: Path to existing torrent file to reuse piece
            hashes from (see :func:`~.utils.torrent.create`)
        :param exclude_files: Sequence of glob patterns (:class:`str`) and
            :class:`re.Pattern` objects that are matched against the relative
            path within the generated torrent

            .. note:: This sequence is added to the ``exclude`` list in
               :class:`~.base.TrackerConfigBase`.
        """
        self._tracker = tracker
        self._content_path = content_path
        self._reuse_torrent_path = reuse_torrent_path
        self._torrent_path = os.path.join(
            self.home_directory,
            f'{fs.basename(content_path)}.{tracker.name.lower()}.torrent',
        )

        self._exclude_files = list(self._tracker.options['exclude'])
        for pattern in exclude_files:
            if not is_regex_pattern(pattern):
                pattern = fnmatch.translate(str(pattern))
            self._exclude_files.append(pattern)

        self.signal.add('announce_url')
        self.signal.add('file_tree')
        self.signal.add('progress_update')
        self._torrent_process = None

    def execute(self):
        """Get announce URL from `tracker`, then execute torrent creation subprocess"""
        if not self.ignore_cache and os.path.exists(self._torrent_path):
            self._handle_torrent_created(self._torrent_path)
            self.finish()
        else:
            self._get_announce_url_task = self.add_task(self._get_announce_url())
            self._get_announce_url_task.add_done_callback(
                lambda task: self._start_torrent_creation_process(task.result())
            )

    async def _get_announce_url(self):
        self.info = 'Getting announce URL'
        self.signal.emit('announce_url', Ellipsis)
        try:
            await self._tracker.login()
            announce_url = await self._tracker.get_announce_url()
        except errors.RequestError as e:
            self.error(e)
        else:
            self.signal.emit('announce_url', announce_url)
            return announce_url
        finally:
            self.info = ''
            try:
                await self._tracker.logout()
            except errors.RequestError as e:
                self.warn(e)

    def _start_torrent_creation_process(self, announce_url):
        self._torrent_process = daemon.DaemonProcess(
            name=self.name,
            target=_torrent_process,
            kwargs={
                'content_path': self._content_path,
                'torrent_path': self._torrent_path,
                'reuse_torrent_path': self._reuse_torrent_path,
                'overwrite': self.ignore_cache,
                'announce': announce_url,
                'source': self._tracker.options['source'],
                'exclude': self._exclude_files,
            },
            init_callback=self._handle_file_tree,
            info_callback=self._handle_info_update,
            error_callback=self._handle_error,
            result_callback=self._handle_torrent_created,
            finished_callback=self.finish,
        )
        self._torrent_process.start()

    def finish(self):
        """Terminate torrent creation subprocess and finish"""
        if self._torrent_process:
            self._torrent_process.stop()
        super().finish()

    def _handle_file_tree(self, file_tree):
        self.signal.emit('file_tree', file_tree)

    def _handle_info_update(self, info):
        if isinstance(info, torrent.CreateTorrentProgress):
            self.signal.emit('progress_update', info)

    def _handle_torrent_created(self, torrent_path=None):
        _log.debug('Torrent created: %r', torrent_path)
        if torrent_path:
            self.send(torrent_path)

    def _handle_error(self, error):
        if isinstance(error, BaseException):
            _log.debug('CreateTorrentJob: Raising %r', error)
            self.exception(error)
        else:
            _log.debug('CreateTorrentJob: Reporting %r', error)
            self.error(error)


def _torrent_process(output_queue, input_queue, *args, **kwargs):
    def terminate_signal_sent():
        try:
            typ, msg = input_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if typ == daemon.MsgType.terminate:
                return True
        return False

    def init_callback(file_tree):
        if terminate_signal_sent():
            return 'cancel'
        else:
            output_queue.put((daemon.MsgType.init, file_tree))

    def progress_callback(progress):
        if terminate_signal_sent():
            return 'cancel'
        else:
            output_queue.put((daemon.MsgType.info, progress))

    def info_callback(message):
        if terminate_signal_sent():
            return 'cancel'
        else:
            output_queue.put((daemon.MsgType.info, message))

    kwargs['init_callback'] = init_callback
    kwargs['progress_callback'] = progress_callback
    kwargs['info_callback'] = info_callback
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
        self.signal.register('adding', lambda tp: setattr(self, 'info', f'Adding {fs.basename(tp)}'))
        self.signal.register('added', lambda _: setattr(self, 'info', ''))
        self.signal.register('finished', lambda _: setattr(self, 'info', ''))
        self.signal.register('error', lambda _: setattr(self, 'info', ''))

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
        except errors.RequestError as e:
            self.error(f'Failed to add {torrent_path} to {self._client.name}: {e}')
        else:
            if torrent_hash:
                self.send(torrent_hash)
                self.signal.emit('added', torrent_hash)


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
        self.signal.register('copying', lambda fp: setattr(self, 'info', f'Copying {fs.basename(fp)}'))
        self.signal.register('copied', lambda _: setattr(self, 'info', ''))
        self.signal.register('finished', lambda _: setattr(self, 'info', ''))
        self.signal.register('error', lambda _: setattr(self, 'info', ''))

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
                msg = e.strerror if e.strerror else str(e)
                self.error(f'Failed to copy {filepath} to {self._destination}: {msg}')
                # Default to original torrent path
                self.send(filepath)
            else:
                self.send(new_path)
                self.signal.emit('copied', new_path)
