"""
Client API for Deluge
"""

import base64
import os
import re

import aiobtclientrpc

from ... import errors, utils
from .base import ClientApiBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class DelugeClientApi(ClientApiBase):
    """
    Deluge API

    References:
        https://github.com/JohnDoee/deluge-client#usage
        https://dev.deluge-torrent.org/wiki/UserGuide/ThinClient
    """

    name = 'deluge'
    label = 'Deluge'

    default_config = {
        'url': '127.0.0.1:58846',
        'username': '',
        'password': '',
        'check_after_add': utils.configfiles.config_value(
            value=utils.types.Bool('no'),
            description=f'Whether to tell {label} to verify pieces after adding the torrent.',
        ),
    }

    @utils.cached_property
    def _rpc(self):
        return aiobtclientrpc.DelugeRPC(
            url=self.config['url'],
            username=self.config['username'] or None,
            password=self.config['password'] or None,
        )

    async def add_torrent(self, torrent_path, download_path=None):
        # Read torrent file
        try:
            torrent_filedump = str(
                base64.b64encode(self.read_torrent_file(torrent_path)),
                encoding='ascii',
            )
        except errors.TorrentError as e:
            raise errors.RequestError(e)

        # Options
        options = {
            # Whether we assume that all files are present for this torrent
            'seed_mode': not bool(self.config['check_after_add']),
            'add_paused': False,
        }
        if download_path:
            options['download_location'] = str(os.path.abspath(download_path))

        # Add torrent
        try:
            async with self._rpc:
                infohash = await self._rpc.call(
                    'core.add_torrent_file',
                    filename=utils.fs.basename(torrent_path),
                    filedump=torrent_filedump,
                    options=options,
                )
                if self.config['check_after_add']:
                    await self._rpc.call('core.force_recheck', [infohash])
                return infohash.lower()

        except aiobtclientrpc.Error as e:
            infohash_regex = re.compile(r'Torrent already in session \(([0-9a-zA-Z]+)\)')
            match = infohash_regex.search(str(e))
            if match:
                return match.group(1).lower()
            else:
                raise errors.RequestError(e)
