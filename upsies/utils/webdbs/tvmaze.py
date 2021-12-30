"""
API for tvmaze.com
"""

import collections
import functools
import json

from ... import errors, utils
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

    default_config = {}

    _url_base = 'http://api.tvmaze.com'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._imdb = ImdbApi()

    def sanitize_query(self, query):
        """Set :attr:`~.common.Query.type` to :attr:`~.types.ReleaseType.unknown`"""
        query = super().sanitize_query(query)
        query.type = ReleaseType.unknown
        return query

    async def search(self, query):
        _log.debug('Searching TVmaze for %s', query)

        if query.id:
            show = await self._get_show(query.id)
            return [_TvmazeSearchResult(show=show, tvmaze_api=self)]

        elif not query.title or query.type is ReleaseType.movie:
            return []

        else:
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

    async def _get_json(self, url):
        response = await http.get(url, cache=True)
        try:
            info = json.loads(response)
            assert isinstance(info, (collections.abc.Mapping, collections.abc.Sequence))
        except (ValueError, TypeError, AssertionError):
            raise errors.RequestError(f'Unexpected search response: {response}')
        else:
            return info

    async def _get_show(self, id):
        url = f'{self._url_base}/shows/{id}?embed[]=cast&embed[]=crew'
        return await self._get_json(url)

    async def cast(self, id):
        if id:
            show = await self._get_show(id)
            cast = show.get('_embedded', {}).get('cast', ())
            return tuple(
                common.Person(item['person']['name'], item['person'].get('url', ''))
                for item in utils.deduplicate(cast, key=lambda item: item['person']['name'])
            )
        return ()

    async def _countries(self, id):
        if id:
            show = await self._get_show(id)
            return _get_countries(show)
        return ()

    async def creators(self, id):
        if id:
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
        return ()

    async def directors(self, id):
        return ()

    async def genres(self, id):
        if id:
            show = await self._get_show(id)
            return _get_genres(show)
        return ()

    async def poster_url(self, id, season=None):
        """
        Return URL of poster image or `None`

        :param season: Return poster for specific season
        """
        if id:
            info = {}
            if season:
                url = f'{self._url_base}/shows/{id}/seasons'
                seasons = await self._get_json(url)
                for s in seasons:
                    if str(s.get('number')) == str(season) and s.get('image'):
                        info = s
                        break
            if not info:
                info = await self._get_show(id)
            return (info.get('image') or {}).get('medium', None)
        return ''

    rating_min = 0.0
    rating_max = 10.0

    async def rating(self, id):
        if id:
            show = await self._get_show(id)
            return show.get('rating', {}).get('average')
        return None

    async def _runtimes(self, id):
        runtimes = {}
        if id:
            show = await self._get_show(id)
            runtime = show.get('runtime', 0)
            if runtime:
                runtimes['default'] = round(int(runtime))
        return runtimes

    async def summary(self, id):
        if id:
            show = await self._get_show(id)
            return _get_summary(show)
        return ''

    async def title_english(self, id):
        if id:
            imdb_id = await self.imdb_id(id)
            if imdb_id:
                return await self._imdb.title_english(imdb_id)
        return ''

    async def title_original(self, id):
        if id:
            imdb_id = await self.imdb_id(id)
            if imdb_id:
                return await self._imdb.title_original(imdb_id)
        return ''

    async def type(self, id):
        # TVmaze does not support movies and we can't distinguish between season
        # and episode by ID.
        return ReleaseType.unknown

    async def url(self, id):
        if id:
            show = await self._get_show(id)
            return show.get('url', '')
        return ''

    async def year(self, id):
        if id:
            show = await self._get_show(id)
            return _get_year(show)
        return ''

    async def imdb_id(self, id):
        """Return IMDb ID for TVmaze ID `id` or `None`"""
        if id:
            show = await self._get_show(id)
            imdb_id = show.get('externals', {}).get('imdb')
            if imdb_id:
                return imdb_id
        return ''

    async def episode(self, id, season, episode):
        """
        Get episode information

        :param id: Show ID
        :param season: Season number
        :param episode: Episode number

        :return: :class:`dict` with these keys:

            - ``date`` (:class:`str` as "YYYY-MM-DD")
            - ``episode`` (:class:`str`)
            - ``season`` (:class:`str`)
            - ``summary`` (:class:`str`)
            - ``title`` (:class:`str`)
            - ``url`` (:class:`str`)
        """
        if id:
            url = f'{self._url_base}/shows/{id}/episodebynumber?season={season}&number={episode}'
            episode = await self._get_json(url)
        else:
            episode = {}
        return {
            'date': episode.get('airdate', ''),
            'episode': str(episode.get('number', '')) or '',
            'season': str(episode.get('season', '')) or '',
            'summary': _get_summary(episode),
            'title': episode.get('name', ''),
            'url': episode.get('url', ''),
        }

    async def status(self, id):
        """Return something like "Running", "Ended" or empty string"""
        if id:
            show = await self._get_show(id)
            return show.get('status')
        return ''


class _TvmazeSearchResult(common.SearchResult):
    def __init__(self, *, show, tvmaze_api):
        return super().__init__(
            cast=functools.partial(tvmaze_api.cast, show['id']),
            countries=_get_countries(show),
            directors=(),
            genres=_get_genres(show),
            id=show['id'],
            summary=_get_summary(show),
            title=show['name'],
            title_english=functools.partial(tvmaze_api.title_english, show['id']),
            title_original=functools.partial(tvmaze_api.title_original, show['id']),
            type=ReleaseType.series,
            url=show['url'],
            year=_get_year(show),
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

def _get_genres(show):
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
                return (name,)
    return ''
