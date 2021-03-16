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
        )
        self._soup_cache[cache_id] = html.parse(text)
        return self._soup_cache[cache_id]

    async def search(self, query):
        _log.debug('Searching TMDb for %s', query)
        if not query.title:
            return []

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
        soup = await self._get_soup(id)
        cards = soup.select('.people > .card')
        cast = []
        for card in cards:
            cast.extend(self._get_persons(card))
        return tuple(cast)

    async def countries(self, id):
        raise NotImplementedError('Country lookup is not implemented for TMDb')

    async def creators(self, id):
        soup = await self._get_soup(id)
        profiles = soup.select('.people > .profile')
        creators = []
        for profile in profiles:
            if profile.find('p', text=re.compile(r'(?i:Creator)')):
                creators.extend(self._get_persons(profile))
        return tuple(creators)

    async def directors(self, id):
        soup = await self._get_soup(id)
        profiles = soup.select('.people > .profile')
        directors = []
        for profile in profiles:
            if profile.find('p', text=re.compile(r'(?i:Director)')):
                directors.extend(self._get_persons(profile))
        return tuple(directors)

    async def keywords(self, id):
        soup = await self._get_soup(id)
        keywords = soup.find(class_='keywords')
        if not keywords:
            return ()
        else:
            keywords = list(keywords.stripped_strings)
            if keywords[0] == 'Keywords':
                keywords.pop(0)
            if 'No keywords have been added.' in keywords:
                keywords.clear()
            return tuple(keywords)

    rating_min = 0.0
    rating_max = 100.0

    async def rating(self, id):
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
        soup = await self._get_soup(id)
        overview = ''.join(soup.find('div', class_='overview').stripped_strings)
        if any(text in overview for text in self._no_overview_texts):
            overview = ''
        return overview

    async def title_english(self, id):
        raise NotImplementedError('English title lookup is not implemented for TMDb')

    async def title_original(self, id):
        # TODO: Original title is supported
        # https://www.themoviedb.org/movie/3405-le-dolce-signore
        raise NotImplementedError('Original title lookup is not implemented for TMDb')

    async def type(self, id):
        raise NotImplementedError('Type lookup is not implemented for TMDb')

    async def url(self, id):
        return f'{self._url_base.rstrip("/")}/{id}'

    async def year(self, id):
        soup = await self._get_soup(id)
        year = ''.join(soup.find(class_='release_date').stripped_strings).strip('()')
        _log.debug(year)
        if len(year) == 4 and year.isdigit():
            return year
        else:
            return ''


class _TmdbSearchResult(common.SearchResult):
    def __init__(self, *, soup, tmdb_api):
        id = self._get_id(soup)
        return super().__init__(
            id=id,
            title=self._get_title(soup),
            type=self._get_type(soup),
            url=self._get_url(soup),
            year=self._get_year(soup),
            cast=functools.partial(tmdb_api.cast, id),
            countries=[],
            director='',
            keywords=functools.partial(tmdb_api.keywords, id),
            summary=functools.partial(tmdb_api.summary, id),
            title_english='',
            title_original='',
        )

    def _get_id(self, soup):
        href = soup.find('a', class_='result').get('href')
        return re.sub(r'^.*/((?:movie|tv)/[0-9]+).*?$', r'\1', href)

    def _get_url(self, soup):
        href = soup.find('a', class_='result').get('href')
        if href.startswith('http'):
            return href
        elif href.startswith('/'):
            return f'{TmdbApi._url_base}{href}'
        else:
            return f'{TmdbApi._url_base}/{href}'

    def _get_type(self, soup):
        href = soup.find('a', class_='result').get('href')
        tmdb_type = re.sub(r'(?:^|/)(\w+)/.*$', r'\1', href)
        if tmdb_type == 'movie':
            return ReleaseType.movie
        elif tmdb_type == 'tv':
            return ReleaseType.series
        else:
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
