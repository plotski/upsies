from base64 import b64decode

from ... import errors
from .. import http
from . import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class PredbovhApi(base.SceneDbApiBase):
    name = 'predbovh'
    label = 'PreDB.ovh'

    default_config = {}

    _url_base = b64decode('cHJlZGIub3Zo').decode('ascii')
    _search_url = f'https://{_url_base}/api/v1/'

    async def _search(self, keywords, group):
        q = self._get_q(keywords, group)
        return await self._request_all_pages(q)

    def _get_q(self, keywords, group):
        if group:
            keywords = list(keywords)
            keywords.extend(('@team', str(group).replace('@', r'\@').strip()))
        kws = (str(kw).lower().strip() for kw in keywords)
        return ' '.join(kw for kw in kws if kw)

    async def _request_all_pages(self, q):
        combined_results = []

        # We can request 30 pages per minute before we get an error
        for page in range(1, 31):
            results, next_page = await self._request_page(q, page)
            combined_results.extend(results)

            # Negative next page means last page
            if next_page < 0:
                break

        return combined_results

    async def _request_page(self, q, page):
        params = {
            'q': q,
            'count': 100,
            'page': page,
        }
        _log.debug('%s search: %r, %r', self.label, self._search_url, params)
        response = (await http.get(self._search_url, params=params, cache=True)).json()

        # Report API error or return list of release names
        if response['status'] != 'success':
            raise errors.RequestError(f'{self.label}: {response["message"]}')
        else:
            # Extract release names
            results = tuple(result['name'] for result in response['data']['rows'])

            # Is there another page of results?
            if len(results) >= response['data']['reqCount']:
                next_page = page + 1
            else:
                next_page = -1

            return results, next_page

    async def release_files(self, release_name):
        """Always return an empty :class:`dict`"""
        return {}
