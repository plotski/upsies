import functools
import json

from .... import errors
from ....utils import http
from .. import _common
from . import _get, _info, _url_base

import logging  # isort:skip
_log = logging.getLogger(__name__)


async def search(title, type=None, year=None):
    """
    Search TVmaze

    :param str title: Name of movie or series
    :param type: Ignored for compatibility with signature of other `search`
        functions
    :param year: Year of release
    :type year: str or int

    :raise RequestError: if the search request fails

    :return: Sequence of SearchResult objects
    """
    title = title.strip()
    _log.debug('Searching TVmaze for %r, type=%r, year=%r', title, type, year)
    if not title:
        return ()

    url = f'{_url_base}/search/shows'
    params = {'q': title}

    results_str = await http.get(url, params=params, cache=True)
    try:
        items = json.loads(results_str)
        assert isinstance(items, list)
    except (ValueError, TypeError, AssertionError):
        raise errors.RequestError(f'Unexpected search response: {results_str}')
    else:
        # The API doesn't allow us to search for a specific year
        results = [_make_result(item['show']) for item in items]
        if year:
            results_in_year = []
            for result in results:
                if str(result.year) == str(year):
                    results_in_year.append(result)
            if results_in_year:
                return results_in_year
        return results


def _make_result(show):
    return _common.SearchResult(
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
