import functools
import json

from .... import errors
from ....utils import http
from .. import common
from . import _get, _info, _url_base

import logging  # isort:skip
_log = logging.getLogger(__name__)


async def search(query):
    """
    Search for TVmaze ID

    :param query: :class:`~tools.dbs.Query` instance

    :raise RequestError: if the search request fails

    :return: Sequence of :class:`~tools.dbs.SearchResult~ objects
    """
    _log.debug('Searching TVmaze for %s', query)
    if not query.title:
        return ()

    url = f'{_url_base}/search/shows'
    params = {'q': query.title}

    results_str = await http.get(url, params=params, cache=True)
    try:
        items = json.loads(results_str)
        assert isinstance(items, list)
    except (ValueError, TypeError, AssertionError):
        raise errors.RequestError(f'Unexpected search response: {results_str}')
    else:
        # The API doesn't allow us to search for a specific year
        results = [_make_result(item['show']) for item in items]
        if query.year:
            results_in_year = []
            for result in results:
                if str(result.year) == query.year:
                    results_in_year.append(result)
            if results_in_year:
                return results_in_year
        return results


def _make_result(show):
    return common.SearchResult(
        id=show['id'],
        url=show['url'],
        type='series',
        title=show['name'],
        year=_get.year(show),
        keywords=_get.genres(show),
        summary=_get.summary(show),
        cast=functools.partial(_info.cast, show['id']),
        country=_get.country(show),
        title_original=functools.partial(_info.title_original, show['id']),
        title_english=functools.partial(_info.title_english, show['id']),
    )
