"""
Client API for Deluge
"""

import base64
import os
import re

import deluge_client

from ... import errors, utils
from .. import asynccontextmanager
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
        'host': '127.0.0.1',
        'port': utils.types.Integer(58846, min=0, max=65535),
        'username': '',
        'password': '',
        'check_after_add': utils.configfiles.config_value(
            value=utils.types.Bool('no'),
            description=f'Whether to tell {label} to verify pieces after adding the torrent.',
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = deluge_client.DelugeRPCClient(
            host=self.config['host'],
            port=self.config['port'],
            username=self.config['username'],
            password=self.config['password'],
        )

    async def _call(self, method_name, *args, **kwargs):
        method = getattr(self._client, method_name)
        try:
            return method(*args, **kwargs)
        except deluge_client.client.DelugeClientException as e:
            raise errors.RequestError(e)

    async def _login(self):
        await self._call('connect')

    async def _logout(self):
        await self._call('disconnect')

    @asynccontextmanager
    async def _session(self):
        await self._login()
        try:
            yield
        finally:
            await self._logout()

    async def add_torrent(self, torrent_path, download_path=None):
        try:
            torrent_filedump = str(
                base64.b64encode(self.read_torrent_file(torrent_path)),
                encoding='ascii',
            )
        except errors.TorrentError as e:
            raise errors.RequestError(e)

        options = {
            # Assume that all files are present for this torrent
            'seed_mode': not bool(self.config['check_after_add']),
        }
        if download_path:
            options['download_location'] = str(os.path.abspath(download_path))

        async with self._session():
            try:
                infohash_bytes = await self._call(
                    'core.add_torrent_file',
                    filename=utils.fs.basename(torrent_path),
                    filedump=torrent_filedump,
                    options=options,
                )
            except errors.RequestError as e:
                infohash_regex = re.compile(r'Torrent already in session \(([0-9a-zA-Z]+)\)')
                match = infohash_regex.search(str(e))
                if match:
                    infohash = match.group(1)
                else:
                    raise
            else:
                infohash = infohash_bytes.decode('ascii')

        return infohash
