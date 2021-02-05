from base64 import b64decode

from .. import http
from . import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SrrDbApi(base.SceneDbApiBase):
    name = 'srrdb'
    label = 'srrDB'

    _url_base = b64decode('d3d3LnNycmRiLmNvbQ==').decode('ascii')
    _search_url = f'https://{_url_base}/api/search'

    async def _search(self, keywords, group, cache):
        if group:
            keywords = list(keywords)
            keywords.append(f'group:{group}')
        search_url = f"{self._search_url}/{'/'.join(keywords)}"
        _log.debug('Scene search URL: %r', search_url)
        response = (await http.get(search_url, cache=cache)).json()
        results = response.get('results', [])
        return (r['release'] for r in results)
