"""
API for tvmaze.com
"""

import functools
import json

from ... import errors
from .. import html, http
from ..types import ReleaseType
from . import common
from .base import WebDbApiBase
from .imdb import ImdbApi

import logging  # isort:skip
_log = logging.getLogger(__name__)


class TvmazeApi(WebDbApiBase):
    """API for tvmaze.com"""

    name = 'tvmaze'
    label = 'TVmaze'
    _url_base = 'http://api.tvmaze.com'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._imdb = ImdbApi()

    async def search(self, query):
        _log.debug('Searching TVmaze for %s', query)
        if not query.title or query.type is ReleaseType.movie:
            return []

        url = f'{self._url_base}/search/shows'
        params = {'q': query.title_normalized}

        results_str = await http.get(url, params=params, cache=True)
        try:
            items = json.loads(results_str)
            assert isinstance(items, list)
        except (ValueError, TypeError, AssertionError):
            raise errors.RequestError(f'Unexpected search response: {results_str}')
        else:
            results = [_TvmazeSearchResult(show=item['show'], tvmaze_api=self)
                       for item in items]
            # The API doesn't allow us to search for a specific year
            if query.year:
                results_in_year = []
                for result in results:
                    if str(result.year) == query.year:
                        results_in_year.append(result)
                return results_in_year
            return results

    async def _get_show(self, id):
        url = f'{self._url_base}/shows/{id}?embed[]=cast&embed[]=crew'
        response = await http.get(url, cache=True)
        try:
            show = json.loads(response)
            assert isinstance(show, dict)
        except (ValueError, TypeError, AssertionError):
            raise errors.RequestError(f'Unexpected search response: {response}')
        else:
            return show

    async def cast(self, id):
        show = await self._get_show(id)
        cast = show.get('_embedded', {}).get('cast', ())
        return tuple(
            common.Person(item['person']['name'], item['person'].get('url', ''))
            for item in cast
        )

    async def countries(self, id):
        show = await self._get_show(id)
        return _get_countries(show)

    async def creators(self, id):
        show = await self._get_show(id)
        crew = show.get('_embedded', {}).get('crew', ())
        creators = []
        for item in crew:
            if item.get('type') == 'Creator' and item.get('person', {}).get('name'):
                creators.append(common.Person(
                    item['person']['name'],
                    item['person'].get('url', ''),
                ))
        return tuple(creators)

    async def directors(self, id):
        return ()

    async def keywords(self, id):
        show = await self._get_show(id)
        return _get_keywords(show)

    async def poster_url(self, id):
        show = await self._get_show(id)
        return show.get('image', {}).get('medium', None)

    rating_min = 0.0
    rating_max = 10.0

    async def rating(self, id):
        show = await self._get_show(id)
        return show.get('rating', {}).get('average')

    async def summary(self, id):
        show = await self._get_show(id)
        return _get_summary(show)

    async def title_english(self, id):
        show = await self._get_show(id)
        imdb_id = show.get('externals', {}).get('imdb')
        if imdb_id:
            return await self._imdb.title_english(imdb_id)
        else:
            return ''

    async def title_original(self, id):
        show = await self._get_show(id)
        imdb_id = show.get('externals', {}).get('imdb')
        _log.debug('Getting original title via imdb id: %r', imdb_id)
        if imdb_id:
            return await self._imdb.title_original(imdb_id)
        else:
            return ''

    async def type(self, id):
        # TVmaze does not support movies and we can't distinguish between season
        # and episode by IMDb ID.
        raise NotImplementedError('Type lookup is not implemented for TVmaze')

    async def url(self, id):
        return f'{self._url_base.rstrip("/")}/shows/{id}'

    async def year(self, id):
        show = await self._get_show(id)
        return _get_year(show)


class _TvmazeSearchResult(common.SearchResult):
    def __init__(self, *, show, tvmaze_api):
        return super().__init__(
            id=show['id'],
            title=show['name'],
            type=ReleaseType.series,
            url=show['url'],
            year=_get_year(show),
            cast=functools.partial(tvmaze_api.cast, show['id']),
            countries=_get_countries(show),
            director='',
            keywords=_get_keywords(show),
            summary=_get_summary(show),
            title_english=functools.partial(tvmaze_api.title_english, show['id']),
            title_original=functools.partial(tvmaze_api.title_original, show['id']),
        )


def _get_summary(show):
    summary = show.get('summary', None)
    if summary:
        soup = html.parse(summary)
        return '\n'.join(paragraph.text for paragraph in soup.find_all('p'))
    else:
        return ''

def _get_year(show):
    premiered = show.get('premiered', None)
    if premiered:
        year = str(premiered).split('-')[0]
        if year.isdigit() and len(year) == 4:
            return year
    else:
        return ''

def _get_keywords(show):
    genres = show.get('genres', None)
    if genres:
        return tuple(str(g).lower() for g in genres)
    else:
        return ()

def _get_countries(show):
    network = show.get('network', None)
    if network:
        country = network.get('country', None)
        if country:
            name = country.get('name', None)
            if name:
                return [name]
    return ''
