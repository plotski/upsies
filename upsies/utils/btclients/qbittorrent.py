"""
Client API for qBittorrent
"""

import os
import urllib

import torf

from ... import errors
from .. import asynccontextmanager, http
from .base import ClientApiBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class QbittorrentClientApi(ClientApiBase):
    """
    qBittorrent API

    Reference: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)
    """

    name = 'qbittorrent'

    default_config = {
        'url': 'http://localhost:8080',
        'username': '',
        'password': '',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        url = urllib.parse.urlparse(self.config['url'])
        self._headers = {
            'Referer': f'{url.scheme}://{url.netloc}',
        }

    async def _request(self, path, data=None, files={}):
        url = '/'.join((
            self.config['url'].rstrip('/'),
            'api/v2',
            path.lstrip('/'),
        ))
        return await http.post(
            url=url,
            headers=self._headers,
            data=data,
            files=files
        )

    async def _login(self):
        credentials = {
            'username': self.config['username'],
            'password': self.config['password'],
        }
        response = await self._request(path='auth/login', data=credentials)
        if response != 'Ok.':
            raise errors.RequestError('Authentication failed')

    async def _logout(self):
        await self._request(path='auth/logout')

    @asynccontextmanager
    async def _session(self):
        await self._login()
        try:
            yield
        finally:
            await self._logout()

    async def add_torrent(self, torrent_path, download_path=None):
        files = {
            'torrents': {
                'file': torrent_path,
                'mimetype': 'application/x-bittorrent',
            },
        }
        data = {}
        if download_path:
            data['savepath'] = str(os.path.abspath(download_path))

        async with self._session():
            response = await self._request('torrents/add', files=files, data=data)
            if response == 'Ok.':
                return self._get_torrent_hash(torrent_path)
            else:
                raise errors.RequestError('Unknown error')

    def _get_torrent_hash(self, torrent_path):
        # TODO: Get the info hash from `response` when this is closed:
        #       https://github.com/qbittorrent/qBittorrent/issues/4879
        #       For older versions of qBittorrent, default to getting the hash
        #       from the torrent file.
        try:
            torrent = torf.Torrent.read(torrent_path)
        except torf.TorfError as e:
            raise errors.RequestError(e)
        else:
            return torrent.infohash
