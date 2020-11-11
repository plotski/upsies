import base64
import json

from ... import errors
from ...utils import http
from . import ClientApiBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


DEFAULT_URL = 'http://localhost:9091/transmission/rpc'
AUTH_ERROR_CODE = 401
CSRF_ERROR_CODE = 409
CSRF_HEADER = 'X-Transmission-Session-Id'


class ClientApi(ClientApiBase):
    """
    RPC for Transmission daemon

    https://github.com/transmission/transmission/blob/master/extras/rpc-spec.txt
    """

    name = 'transmission'

    def __init__(self, username='', password='', url=None):
        self._username = username
        self._password = password
        self._url = url or DEFAULT_URL
        self._headers = {'Content-Type': 'application/json'}

    async def _request(self, data):
        if self._username or self._password:
            auth = (self._username, self._password)
        else:
            auth = None

        try:
            response = await http.post(
                url=self._url,
                headers=self._headers,
                auth=auth,
                data=data,
            )
        except errors.RequestError as e:
            if e.status_code == CSRF_ERROR_CODE:
                # Send same request again with CSRF header
                self._headers[CSRF_HEADER] = e.headers[CSRF_HEADER]
                return await self._request(data)
            elif e.status_code == AUTH_ERROR_CODE:
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
            request['arguments']['download-dir'] = str(download_path)

        info = await self._request(json.dumps(request))
        arguments = info.get('arguments', {})
        if 'torrent-added' in arguments:
            return arguments['torrent-added']['id']
        elif 'torrent-duplicate' in arguments:
            return arguments['torrent-duplicate']['id']
        elif 'result' in info:
            raise errors.TorrentError(str(info['result']).capitalize())
        else:
            raise errors.TorrentError('Adding failed for unknown reason')
