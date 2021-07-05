from base64 import b64decode

from ... import errors
from .. import http
from . import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class PreDbApi(base.SceneDbApiBase):
    name = 'predb'
    label = 'PreDB'

    default_config = {}

    _url_base = b64decode('cHJlZGIub3Zo').decode('ascii')
    _search_url = f'https://{_url_base}/api/v1/'

    async def _search(self, keywords, group):
        if group:
            keywords = list(keywords)
            keywords.extend(('@team', str(group).replace('@', r'\@')))
        params = {'q': ' '.join((kw.lower() for kw in keywords)), 'count': 1000}
        _log.debug('Scene search: %r, %r', self._search_url, params)

        response = (await http.get(self._search_url, params=params, cache=True)).json()

        # Report API error or return list of release names
        if response['status'] != 'success':
            raise errors.RequestError(f'{self.label}: {response["message"]}')
        else:
            return (result['name'] for result in response['data']['rows'])

    async def release_files(self, release_name):
        """Always return an empty :class:`dict`"""
        return {}
