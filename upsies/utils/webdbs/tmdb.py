"""
API for themoviedb.org
"""

import functools
import re

from ... import errors
from .. import ReleaseType, html, http
from . import common
from .base import WebDbApiBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class TmdbApi(WebDbApiBase):
    """API for themoviedb.org"""

    name = 'tmdb'
    label = 'TMDb'
    _url_base = 'http://themoviedb.org'

    async def search(self, query):
        _log.debug('Searching TMDb for %s', query)
        if not query.title:
            return []

        params = {'query': query.title}
        if query.year is not None:
            params['query'] += f' y:{query.year}'
        if query.type is ReleaseType.movie:
            url = f'{self._url_base}/search/movie'
        elif query.type in (ReleaseType.series, ReleaseType.season, ReleaseType.episode):
            url = f'{self._url_base}/search/tv'
        else:
            url = f'{self._url_base}/search'

        text = await http.get(url, params=params, cache=True)
        soup = html.parse(text)

        # When search for year, unmatching results are included but hidden.
        for tag in soup.find_all('div', class_='hide'):
            tag.clear()

        items = soup.find_all('div', class_='card')
        return [_TmdbSearchResult(soup=item, tmdb_api=self)
                for item in items]

    async def cast(self, id):
        try:
            text = await http.get(f'{self._url_base}/{id}', cache=True)
        except errors.RequestError:
            return ''

        soup = html.parse(text)
        cards = soup.select('.people > .card')
        cast = []
        for card in cards:
            for link in card.find_all('a'):
                strings = list(link.stripped_strings)
                if strings:
                    cast.append(strings[0])
        return cast

    async def countries(self, id):
        raise NotImplementedError('Country lookup is not implemented for TMDb')

    async def keywords(self, id):
        try:
            text = await http.get(f'{self._url_base}/{id}', cache=True)
        except errors.RequestError:
            return ''

        soup = html.parse(text)
        keywords = soup.find(class_='keywords')
        if not keywords:
            return []
        else:
            keywords = list(keywords.stripped_strings)
            if keywords[0] == 'Keywords':
                keywords.pop(0)
            if 'No keywords have been added.' in keywords:
                keywords.clear()
            return keywords

    _no_overview_texts = (
        "We don't have an overview",
        'No overview found.',
    )

    async def summary(self, id):
        try:
            text = await http.get(f'{self._url_base}/{id}', cache=True)
        except errors.RequestError:
            return ''

        soup = html.parse(text)
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

    async def year(self, id):
        try:
            text = await http.get(f'{self._url_base}/{id}', cache=True)
        except errors.RequestError:
            return ''

        soup = html.parse(text)
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
