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

    async def search(self, *query, group=None, cache=True):
        query = self._normalize_query(query)
        if group:
            query.append(f'group:{group}')
        search_url = f"{self._search_url}/{'/'.join(query)}"
        _log.debug('Scene search URL: %r', search_url)

        # Get search results
        response = (await http.get(search_url, cache=cache)).json()
        results = response.get('results', [])
        return self._normalize_results((r['release'] for r in results))
