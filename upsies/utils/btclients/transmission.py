"""
Client API for the Transmission daemon
"""

import base64
import os

import aiobtclientrpc

from ... import errors, utils
from .base import ClientApiBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class TransmissionClientApi(ClientApiBase):
    """
    Transmission daemon API

    Reference: https://github.com/transmission/transmission/blob/master/extras/rpc-spec.txt
    """

    name = 'transmission'
    label = 'Transmission'

    default_config = {
        'url': 'http://localhost:9091/transmission/rpc',
        'username': '',
        'password': '',
    }

    @utils.cached_property
    def _rpc(self):
        return aiobtclientrpc.TransmissionRPC(
            url=self.config['url'],
            username=self.config['username'],
            password=self.config['password'],
        )

    async def add_torrent(self, torrent_path, download_path=None):
        args = {}

        # Read torrent file
        try:
            args['metainfo'] = str(
                base64.b64encode(self.read_torrent_file(torrent_path)),
                encoding='ascii',
            )
        except errors.TorrentError as e:
            raise errors.RequestError(e)

        # Non-default download path
        if download_path:
            args['download-dir'] = str(os.path.abspath(download_path))

        # Add torrent
        try:
            async with self._rpc:
                response = await self._rpc.call('torrent-add', args)
        except aiobtclientrpc.Error as e:
            raise errors.RequestError(e)

        print('response:', response)

        # Get torrent hash or error message
        arguments = response.get('arguments', {})
        if 'torrent-added' in arguments:
            return arguments['torrent-added']['hashString']
        elif 'torrent-duplicate' in arguments:
            return arguments['torrent-duplicate']['hashString']
        else:
            raise RuntimeError(f'Unexpected response: {response}')
