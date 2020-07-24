import json

from async_lru import alru_cache

from .... import errors
from ....utils import http
from .. import imdb
from . import _get, _url_base

import logging  # isort:skip
_log = logging.getLogger(__name__)


async def _get_show(id):
    url = f'{_url_base}/shows/{id}'
    params = {'embed': 'cast'}
    response = await http.get(url, params=params, cache=True)
    try:
        show = json.loads(response)
        assert isinstance(show, dict)
    except (ValueError, TypeError, AssertionError):
        raise errors.RequestError(f'Unexpected search response: {response}')
    else:
        return show


@alru_cache(maxsize=None)
async def summary(id):
    """
    Get summary for movie or series

    :param str id: TVmaze ID
    """
    show = await _get_show(id)
    return _get.summary(show)


@alru_cache(maxsize=None)
async def year(id):
    """
    Return release year

    :param str id: TVmaze ID
    """
    show = await _get_show(id)
    return _get.year(show)


@alru_cache(maxsize=None)
async def title_original(id):
    """
    Return original title (e.g. non-English) or empty string

    :param str id: TVmaze ID
    """
    show = await _get_show(id)
    imdb_id = show.get('externals', {}).get('imdb')
    _log.debug('Getting original title via imdb id: %r', imdb_id)
    if imdb_id:
        return await imdb.title_original(imdb_id)
    else:
        return ''


@alru_cache(maxsize=None)
async def title_english(id):
    """
    Return English title if it differs from original title

    :param str id: TVmaze ID
    """
    show = await _get_show(id)
    imdb_id = show.get('externals', {}).get('imdb')
    if imdb_id:
        return await imdb.title_english(imdb_id)
    else:
        return ''


@alru_cache(maxsize=None)
async def cast(id):
    show = await _get_show(id)
    cast = show.get('_embedded', {}).get('cast', ())
    return tuple(str(c['person']['name']) for c in cast)
