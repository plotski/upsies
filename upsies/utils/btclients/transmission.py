"""
Client API for the Transmission daemon
"""

import base64
import json
import os

from ... import errors
from .. import http
from .base import ClientApiBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class TransmissionClientApi(ClientApiBase):
    """
    Transmission daemon API

    Reference: https://github.com/transmission/transmission/blob/master/extras/rpc-spec.txt

    :param str username: Username used for authentication
    :param str password: Password used for authentication
    :param str url: Transmission RPC URL, defaults to
        "http://localhost:9091/transmission/rpc"
    """

    DEFAULT_URL = 'http://localhost:9091/transmission/rpc'
    AUTH_ERROR_CODE = 401
    CSRF_ERROR_CODE = 409
    CSRF_HEADER = 'X-Transmission-Session-Id'
    HEADERS = {
        'Content-Type': 'application/json',
    }

    name = 'transmission'

    default_config = {
        'url': DEFAULT_URL,
        'username': '',
        'password': '',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._headers = self.HEADERS.copy()

    async def _request(self, data):
        if self.config['username'] or self.config['password']:
            auth = (self.config['username'], self.config['password'])
        else:
            auth = None

        try:
            response = await http.post(
                url=self.config['url'],
                headers=self._headers,
                auth=auth,
                data=data,
            )
        except errors.RequestError as e:
            if e.status_code == self.CSRF_ERROR_CODE:
                # Send same request again with CSRF header
                self._headers[self.CSRF_HEADER] = e.headers[self.CSRF_HEADER]
                return await self._request(data)
            elif e.status_code == self.AUTH_ERROR_CODE:
                raise errors.TorrentError('Authentication failed')
            else:
                raise errors.TorrentError(e)

        try:
            return response.json()
        except errors.RequestError as e:
            raise errors.TorrentError(e)

    async def add_torrent(self, torrent_path, download_path=None):
        torrent_data = str(
            base64.b64encode(self.read_torrent_file(torrent_path)),
            encoding='ascii',
        )
        request = {
            'method' : 'torrent-add',
            'arguments' : {
                'metainfo': torrent_data,
            },
        }
        if download_path:
            request['arguments']['download-dir'] = str(os.path.abspath(download_path))

        info = await self._request(json.dumps(request))
        arguments = info.get('arguments', {})
        if 'torrent-added' in arguments:
            return arguments['torrent-added']['hashString']
        elif 'torrent-duplicate' in arguments:
            return arguments['torrent-duplicate']['hashString']
        elif 'result' in info:
            raise errors.TorrentError(str(info['result']).capitalize())
        else:
            raise RuntimeError(f'Unexpected response: {info}')
