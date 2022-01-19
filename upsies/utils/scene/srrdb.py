import re
from base64 import b64decode

from .. import http
from . import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SrrdbApi(base.SceneDbApiBase):
    name = 'srrdb'
    label = 'srrDB'

    default_config = {}

    _url_base = b64decode('YXBpLnNycmRiLmNvbQ==').decode('ascii')
    _search_url = f'https://{_url_base}/v1/search'
    _details_url = f'https://{_url_base}/v1/details'

    _keyword_separators_regex = re.compile(r'[,]')

    async def _search(self, keywords, group):
        if group:
            keywords = list(keywords)
            keywords.append(f'group:{group}')

        keywords_path = '/'.join(
            kw.lower()
            for keyword in keywords
            for kw in self._keyword_separators_regex.split(keyword)
        )

        search_url = f'{self._search_url}/{keywords_path}'
        _log.debug('Scene search URL: %r', search_url)
        response = (await http.get(search_url, cache=True)).json()
        results = response.get('results', [])
        return (r['release'] for r in results)

    async def release_files(self, release_name):
        """
        Map file names to dictionaries with the keys ``release_name``,
        ``file_name``, ``size`` and ``crc``

        :param str release_name: Exact name of the release

        :raise RequestError: if request fails
        """
        details_url = f'{self._details_url}/{release_name}'
        _log.debug('Scene details URL: %r', details_url)
        response = (await http.get(details_url, cache=True)).json()
        if not response:
            return {}
        else:
            files = response.get('archived-files', ())
            release_name = response.get('name', '')
            return {
                f['name']: {
                    'release_name': release_name,
                    'file_name': f['name'],
                    'size': f['size'],
                    'crc': f['crc'],
                }
                for f in sorted(files, key=lambda f: f['name'].casefold())
            }
