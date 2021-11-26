"""
Base class for client APIs
"""

import abc
import copy

import torf

from ... import errors


class ClientApiBase(abc.ABC):
    """
    Base class for all BitTorrent client APIs
    """

    def __init__(self, config=None):
        self._config = copy.deepcopy(self.default_config)
        if config is not None:
            self._config.update(config.items())

    @property
    @abc.abstractmethod
    def name(self):
        """Lowercase name of the BitTorrent client"""

    @property
    @abc.abstractmethod
    def label(self):
        """Properly capitalized :attr:`name` of the BitTorrent client"""

    @property
    def config(self):
        """
        User configuration

        This is a deep copy of :attr:`default_config` that is updated with the
        `config` argument from initialization.
        """
        return self._config

    @property
    @abc.abstractmethod
    def default_config(self):
        """Default user configuration as a dictionary"""

    @abc.abstractmethod
    async def add_torrent(self, torrent_path, download_path=None):
        """
        Add torrent to client

        :param str torrent_path: Path to torrent file
        :param str download_path: Path to the directory where the torrent's
            content is or `None` to use the client's default

        :raise RequestError: if adding `torrent_path` fails

        :return: Info hash of the added torrent
        """

    @staticmethod
    def read_torrent_file(torrent_path):
        """
        Return :class:`bytes` from torrent file

        :param str torrent_path: Path to torrent file

        :raise TorrentError: if reading from `torrent_path` fails
        """
        try:
            with open(torrent_path, 'rb') as f:
                return f.read()
        except OSError as e:
            raise errors.TorrentError(f'{torrent_path}: {e.strerror}')

    @staticmethod
    def read_torrent(torrent_path):
        """
        Return :class:`~torf.Torrent` object

        :param str torrent_path: Path to torrent file

        :raise TorrentError: if reading from `torrent_path` fails
        """
        try:
            return torf.Torrent.read(torrent_path)
        except torf.TorfError as e:
            raise errors.TorrentError(e)
