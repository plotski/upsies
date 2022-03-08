"""
Client API for qBittorrent
"""

import asyncio
import os

import aiobtclientrpc

from ... import errors, utils
from .base import ClientApiBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class QbittorrentClientApi(ClientApiBase):
    """
    qBittorrent API

    Reference: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)
    """

    name = 'qbittorrent'
    label = 'qBittorrent'

    default_config = {
        'url': 'http://localhost:8080',
        'username': '',
        'password': '',
        'check_after_add': utils.configfiles.config_value(
            value=utils.types.Bool('no'),
            description=f'Whether to tell {label} to verify pieces after adding the torrent.',
        ),
    }

    @utils.cached_property
    def _rpc(self):
        return aiobtclientrpc.QbittorrentRPC(
            url=self.config['url'],
            username=self.config['username'] or None,
            password=self.config['password'] or None,
        )

    async def add_torrent(self, torrent_path, download_path=None):
        # Read torrent file
        try:
            files = [
                ('filename', (
                    os.path.basename(torrent_path),        # File name
                    self.read_torrent_file(torrent_path),  # File content
                    'application/x-bittorrent',            # MIME type
                )),
            ]
            # TODO: Get the info hash from `response` when this is closed:
            #       https://github.com/qbittorrent/qBittorrent/issues/4879
            #       For older versions of qBittorrent, default to getting the
            #       hash from the torrent file.
            infohash = self.read_torrent(torrent_path).infohash
        except errors.TorrentError as e:
            raise errors.RequestError(e)

        # Options
        options = {
            'skip_checking': 'false' if self.config['check_after_add'] else 'true',
        }
        if download_path:
            options['savepath'] = str(os.path.abspath(download_path))

        # Add torrent
        try:
            async with self._rpc:
                await self._rpc.call('torrents/add', files=files, **options)
                await self._wait_for_added_torrent(infohash)
                return infohash
        except aiobtclientrpc.Error as e:
            raise errors.RequestError(e)

    _add_torrent_timeout = 10
    _add_torrent_check_delay = 0.5

    async def _wait_for_added_torrent(self, infohash):
        aioloop = asyncio.get_event_loop()
        start_time = aioloop.time()
        while aioloop.time() - start_time < self._add_torrent_timeout:
            infohashes = await self._get_torrent_hashes(infohash)
            if infohash in infohashes:
                return
            else:
                await asyncio.sleep(self._add_torrent_check_delay)
        raise errors.RequestError('Unknown error')

    async def _get_torrent_hashes(self, *infohashes):
        infohashes = await self._rpc.call('torrents/info', hashes=infohashes)
        return tuple(infohash['hash'].lower() for infohash in infohashes)
