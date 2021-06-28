"""
API for themoviedb.org
"""

import functools
import re

from .. import html, http
from ..types import ReleaseType
from . import common
from .base import WebDbApiBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class TmdbApi(WebDbApiBase):
    """API for themoviedb.org"""

    name = 'tmdb'
    label = 'TMDb'

    default_config = {}

    _url_base = 'http://themoviedb.org'
    _soup_cache = {}

    async def _get_soup(self, path, params={}):
        cache_id = (path, tuple(sorted(params.items())))
        if cache_id in self._soup_cache:
            return self._soup_cache[cache_id]
        text = await http.get(
            url=f'{self._url_base}/{path.lstrip("/")}',
            params=params,
            cache=True,
            user_agent='Mozilla/5.0 (compatible; MSIE 8.0; Windows NT 6.3; Win64; x64)',
        )
        self._soup_cache[cache_id] = html.parse(text)
        return self._soup_cache[cache_id]

    async def search(self, query):
        _log.debug('Searching TMDb for %s', query)

        if query.id:
            async def generate_result(id):
                _log.debug('Getting ID: %r', id)
                return _TmdbSearchResult(
                    tmdb_api=self,
                    cast=functools.partial(self.cast, id),
                    directors=functools.partial(self.directors, id),
                    genres=functools.partial(self.genres, id),
                    id=id,
                    summary=functools.partial(self.summary, id),
                    title=await self.title_english(id),
                    title_english=functools.partial(self.title_english, id),
                    title_original=functools.partial(self.title_original, id),
                    type=await self.type(id),
                    url=await self.url(id),
                    year=await self.year(id),
                )

            if re.search(r'\b(?:movie|tv)\b', query.id):
                return [await generate_result(query.id)]
            else:
                return [await generate_result(f'movie/{query.id}'),
                        await generate_result(f'tv/{query.id}')]

        elif not query.title:
            return []

        else:
            params = {'query': query.title_normalized}
            if query.year is not None:
                params['query'] += f' y:{query.year}'

            if query.type is ReleaseType.movie:
                soup = await self._get_soup('/search/movie', params=params)
            elif query.type in (ReleaseType.season, ReleaseType.episode):
                soup = await self._get_soup('/search/tv', params=params)
            else:
                soup = await self._get_soup('/search', params=params)

            # When search for year, unmatching results are included but hidden.
            for tag in soup.find_all('div', class_='hide'):
                tag.clear()

            items = soup.find_all('div', class_='card')
            return [_TmdbSearchResult(soup=item, tmdb_api=self)
                    for item in items]

    _person_url_path_regex = re.compile(r'(/person/\d+[-a-z]+)')

    def _get_persons(self, tag):
        a_tags = tag.find_all('a', href=self._person_url_path_regex)
        persons = []
        for a_tag in a_tags:
            if a_tag.string:
                name = a_tag.string.strip()
                url_path = self._person_url_path_regex.match(a_tag["href"]).group(1)
                url = f'{self._url_base.rstrip("/")}/{url_path.lstrip("/")}'
                persons.append(common.Person(name, url))
        return tuple(persons)

    async def cast(self, id):
        cast = []
        if id:
            soup = await self._get_soup(id)
            cards = soup.select('.people > .card')
            for card in cards:
                cast.extend(self._get_persons(card))
        return tuple(cast)

    async def countries(self, id):
        raise NotImplementedError('Country lookup is not implemented for TMDb')

    async def creators(self, id):
        creators = []
        if id:
            soup = await self._get_soup(id)
            profiles = soup.select('.people > .profile')
            for profile in profiles:
                if profile.find('p', text=re.compile(r'(?i:Creator)')):
                    creators.extend(self._get_persons(profile))
        return tuple(creators)

    async def directors(self, id):
        directors = []
        if id:
            soup = await self._get_soup(id)
            profiles = soup.select('.people > .profile')
            for profile in profiles:
                if profile.find('p', text=re.compile(r'(?i:Director)')):
                    directors.extend(self._get_persons(profile))
        return tuple(directors)

    async def genres(self, id):
        genres = ()
        if id:
            soup = await self._get_soup(id)
            genres_tag = soup.find(class_='genres')
            if genres_tag:
                genres = (k.lower() for k in genres_tag.stripped_strings
                          if k != ',')
        return tuple(genres)

    async def poster_url(self, id):
        if id:
            soup = await self._get_soup(id)
            img_tag = soup.find('img', class_='poster')
            if img_tag:
                srcs = img_tag.get('data-srcset')
                if srcs:
                    path = srcs.split()[0]
                    return f'{self._url_base.rstrip("/")}/{path.lstrip("/")}'
        return ''

    rating_min = 0.0
    rating_max = 100.0

    async def rating(self, id):
        if id:
            soup = await self._get_soup(id)
            rating_tag = soup.find(class_='user_score_chart')
            if rating_tag:
                try:
                    return float(rating_tag['data-percent'])
                except (ValueError, TypeError):
                    pass

    _no_overview_texts = (
        "We don't have an overview",
        'No overview found.',
    )

    async def summary(self, id):
        if id:
            soup = await self._get_soup(id)
            overview = ''.join(soup.find('div', class_='overview').stripped_strings)
            if any(text in overview for text in self._no_overview_texts):
                overview = ''
            return overview
        return ''

    async def title_english(self, id):
        if id:
            soup = await self._get_soup(id)
            title_tag = soup.find(class_='title')
            if title_tag:
                title_parts = list(title_tag.stripped_strings)
                if title_parts:
                    return title_parts[0]
        return ''

    async def title_original(self, id):
        if id:
            soup = await self._get_soup(id)
            title_tag = soup.find(string=re.compile(r'Original (?:Title|Name)'))
            if title_tag:
                try:
                    parent_tag = title_tag.parent.parent
                except AttributeError:
                    pass
                else:
                    strings = tuple(parent_tag.stripped_strings)
                    if len(strings) >= 2:
                        return strings[1]
        return await self.title_english(id)

    async def type(self, id):
        if id:
            soup = await self._get_soup(id)
            network_tag = soup.find('bdi', string=re.compile(r'^Networks?$'))
            if network_tag:
                return ReleaseType.series
            else:
                return ReleaseType.movie
        else:
            return ReleaseType.unknown

    async def url(self, id):
        if id:
            return f'{self._url_base.rstrip("/")}/{id.strip("/")}'
        return ''

    async def year(self, id):
        if id:
            soup = await self._get_soup(id)
            release_date_tag = soup.find(class_='release_date')
            if release_date_tag:
                year = ''.join(release_date_tag.stripped_strings).strip('()')
                if len(year) == 4 and year.isdigit():
                    return year
        return ''


class _TmdbSearchResult(common.SearchResult):
    def __init__(self, *, tmdb_api, soup=None, cast=None, countries=None,
                 directors=None, id=None, genres=None, summary=None, title=None,
                 title_english=None, title_original=None, type=None, url=None,
                 year=None):
        soup = soup or html.parse('')
        id = id or self._get_id(soup)
        return super().__init__(
            cast=cast or functools.partial(tmdb_api.cast, id),
            countries=countries or (),
            directors=directors or functools.partial(tmdb_api.directors, id),
            id=id,
            genres=genres or functools.partial(tmdb_api.genres, id),
            summary=summary or functools.partial(tmdb_api.summary, id),
            title=title or self._get_title(soup),
            title_english=title_english or functools.partial(tmdb_api.title_english, id),
            title_original=title_original or functools.partial(tmdb_api.title_original, id),
            type=type or self._get_type(soup),
            url=url or self._get_url(soup),
            year=year or self._get_year(soup),
        )

    def _get_id(self, soup):
        a_tag = soup.find('a', class_='result')
        if a_tag:
            href = a_tag.get('href')
            return re.sub(r'^.*/((?:movie|tv)/[0-9]+).*?$', r'\1', href)
        return ''

    def _get_url(self, soup):
        a_tag = soup.find('a', class_='result')
        if a_tag:
            href = a_tag.get('href')
            if href.startswith('http'):
                return href
            elif href.startswith('/'):
                return f'{TmdbApi._url_base}{href}'
            elif href:
                return f'{TmdbApi._url_base}/{href}'
        return ''

    def _get_type(self, soup):
        a_tag = soup.find('a', class_='result')
        if a_tag:
            href = a_tag.get('href')
            if href:
                tmdb_type = re.sub(r'(?:^|/)(\w+)/.*$', r'\1', href)
                if tmdb_type == 'movie':
                    return ReleaseType.movie
                elif tmdb_type == 'tv':
                    return ReleaseType.series
        return ReleaseType.unknown

    def _get_title(self, soup):
        header = soup.select('.result > h2')
        if header:
            return header[0].string
        else:
            return ''

    def _get_year(self, soup):
        release_date = soup.find(class_='release_date')
        if release_date:
            match = re.search(r'(\d{4})$', release_date.string)
            if match:
                return match.group(1)
        return ''
