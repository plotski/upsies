"""
Base class for client APIs
"""

import abc

from ... import errors


class ClientApiBase(abc.ABC):
    """
    Base class for all BitTorrent client APIs
    """

    @property
    @abc.abstractmethod
    def name(self):
        """Name of the BitTorrent client"""

    @abc.abstractmethod
    def add_torrent(self, torrent_path, download_path=None):
        """
        Add torrent to client

        :param str torrent_path: Path to torrent file
        :param str download_path: Path to the directory where the torrent's
            content is or `None` to use the client's default

        :raise TorrentError: if adding `torrent_path` fails

        :return: Info hash of the added torrent
        """

    @staticmethod
    def read_torrent_file(torrent_path):
        """
        Return bytes from torrent file

        :param str torrent_path: Path to torrent file

        :raise TorrentError: if reading from `torrent_path` fails
        """
        try:
            with open(torrent_path, 'rb') as f:
                return f.read()
        except OSError as e:
            raise errors.TorrentError(f'{torrent_path}: {e.strerror}')
