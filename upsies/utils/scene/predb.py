from base64 import b64decode

from ... import errors
from .. import http
from . import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class PreDbApi(base.SceneDbApiBase):
    name = 'predb'
    label = 'PreDB'

    _url_base = b64decode('cHJlZGIub3Zo').decode('ascii')
    _search_url = f'https://{_url_base}/api/v1/'

    async def _search(self, *, query, group, cache):
        # Build query
        if group:
            query.extend(('@team', str(group)))

        # Get search results
        params = {'q': ' '.join(query)}
        _log.debug('Scene search: %r, %r', self._search_url, params)
        response = (await http.get(self._search_url, params=params, cache=cache)).json()

        # Report error or return list of release names
        if response['status'] != 'success':
            raise errors.SceneError(f'{self.label}: {response["message"]}')
        else:
            return (result['name'] for result in response['data']['rows'])
