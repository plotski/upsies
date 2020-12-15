import asyncio
import builtins
import collections
import functools
import json
import os
import re
import string

from ... import utils
from . import common
from .base import WebDbApiBase

import logging  # isort:skip
_log = logging.getLogger(__name__)

imdbpie = utils.LazyModule(module='imdbpie', namespace=globals())
bs4 = utils.LazyModule(module='bs4', namespace=globals())


class ImdbApi(WebDbApiBase):
    """API for imdb.com"""

    name = 'imdb'
    label = 'IMDb'
    _url_base = 'http://imdb.com'

    def __init__(self):
        self._imdbpie = _ImdbPie()

    # Scraping IMDb's advanced search website is slower but lets us specify type
    # and year.

    _title_types = {
        utils.ReleaseType.movie: 'feature,tv_movie,documentary,short,video,tv_short',
        utils.ReleaseType.series: 'tv_series,tv_miniseries',
        utils.ReleaseType.season: 'tv_series,tv_miniseries',
        # Searching for single episodes is currently not supported
        utils.ReleaseType.episode: 'tv_series,tv_miniseries',
    }

    async def search(self, query):
        _log.debug('Searching IMDb for %s', query)
        if not query.title:
            return []

        url = f'{self._url_base}/search/title/'
        params = {'title': query.title}
        if query.type is not utils.ReleaseType.unknown:
            params['title_type'] = self._title_types[query.type]
        if query.year is not None:
            params['release_date'] = f'{query.year}-01-01,{query.year}-12-31'

        html = await utils.http.get(url, params=params, cache=True)
        soup = bs4.BeautifulSoup(html, features='html.parser')

        items = soup.find_all('div', class_='lister-item-content')
        results = [_ImdbSearchResult(soup=item, imdb_api=self)
                   for item in items]
        return results

    async def cast(self, id):
        info = await self._imdbpie.get(id, 'title_credits')
        cast = []
        try:
            for member in info['credits']['cast'][:20]:
                cast.append(member['name'])
            return cast
        except KeyError:
            return []

    async def country(self, id):
        info = await self._imdbpie.get(id, 'title_versions')
        codes = info.get('origins', '')  # Two-letter code (ISO 3166-1 alpha-2)
        if codes:
            from ...utils import country
            return country.iso3166_alpha2_name.get(codes[0], '')
        else:
            return ''

    async def keywords(self, id):
        info = await self._imdbpie.get(id, 'title_genres')
        try:
            return [str(g).lower() for g in info['genres'][:5]]
        except KeyError:
            return []

    async def summary(self, id):
        info = await self._imdbpie.get(id)
        try:
            return info['plot']['outline']['text']
        except KeyError:
            try:
                return info['plot']['summaries'][0]['text']
            except (KeyError, IndexError):
                pass
        return ''

    async def title_english(self, id):
        info = await self._imdbpie.get(id, 'title_versions')

        ignored_attributes = ( 'dubbed version', 'literal title', 'original script title',
                               'short title', 'video box title')
        ignored_types = ('working', 'tv')

        # Some titles should not be considered
        def title_looks_interesting(info):
            # Maybe we can just move any title that has an "attributes" field?
            if any(a in info.get('attributes', ()) for a in ignored_attributes):
                return False
            if any(t in info.get('types', ()) for t in ignored_types):
                return False
            return True

        alternate_titles = [
            info for info in sorted(info.get('alternateTitles', ()),
                                    key=lambda x: x.get('region', ''))
            if title_looks_interesting(info)
        ]

        # Map titles to region and language.
        # Both region and language may not exist or be empty.
        # Ensure regions are upper case and languages are lower case.
        titles = collections.defaultdict(lambda: [])
        for info in alternate_titles:
            language = info.get('language', '').lower()
            region = info.get('region', '').upper()
            if language:
                titles[language] = info['title']
            if region:
                titles[region] = info['title']
            if region and language:
                titles[(region, language)] = info['title']

        original_title = await self.title_original(id)
        _log.debug('Original title: %r', original_title)

        # Find English title. US titles seem to be the most commonly used, but they
        # can also be in Spanish.
        priorities = (
            ('US', 'en'),
            'US',
            ('XWW', 'en'),  # World-wide
        )
        for key in priorities:
            if key in titles:
                if self._normalize_title(titles[key]) != self._normalize_title(original_title):
                    _log.debug('English title: %s: %r', key, titles[key])
                    return titles[key]

        return ''

    @staticmethod
    def _normalize_title(title):
        """Return casefolded `title` with any punctuation removed"""
        trans = title.maketrans('', '', string.punctuation)
        return title.translate(trans).casefold()

    async def title_original(self, id):
        info = await self._imdbpie.get(id, 'title_versions')
        return info.get('originalTitle', '')

    async def type(self, id):
        info = await self._imdbpie.get(id)
        title_type = info.get('base', {}).get('titleType', '').casefold()
        if 'movie' in title_type:
            return utils.ReleaseType.movie
        elif 'series' in title_type:
            return utils.ReleaseType.season
        elif 'episode' in title_type:
            return utils.ReleaseType.episode
        else:
            return utils.ReleaseType.unknown

    async def year(self, id):
        info = await self._imdbpie.get(id, 'title')
        return str(info.get('base', {}).get('year', ''))


class _ImdbSearchResult(common.SearchResult):
    def __init__(self, *, soup, imdb_api):
        id = self._get_id(soup)
        return super().__init__(
            cast=self._get_cast(soup),
            country=functools.partial(imdb_api.country, id),
            director=self._get_director(soup),
            id=self._get_id(soup),
            keywords=self._get_keywords(soup),
            summary=self._get_summary(soup),
            title=self._get_title(soup),
            title_english=functools.partial(imdb_api.title_english, id),
            title_original=functools.partial(imdb_api.title_original, id),
            type=self._get_type(soup),
            url=self._get_url(soup),
            year=self._get_year(soup),
        )

    def _get_cast(self, soup):
        people = soup.find(string=re.compile(r'Stars?.*'))
        if people:
            names = [name.string.strip() for name in people.parent.find_all('a')]
            return names[1:]
        else:
            return []

    def _get_id(self, soup):
        href = soup.find('a').get('href')
        return re.sub(r'^.*/([t0-9]+)/.*$', r'\1', href)

    def _get_director(self, soup):
        people = soup.find(string=re.compile(r'Director?.*'))
        if people:
            director = people.parent.find('a')
            if director:
                return director.string.strip()
        else:
            return ''

    def _get_keywords(self, soup):
        try:
            keywords = soup.find(class_='genre').string.strip()
        except AttributeError:
            keywords = ''
        return [kw.strip().casefold() for kw in keywords.split(',')]

    def _get_summary(self, soup):
        tags = soup.find_all(class_='text-muted')
        return (tags[2].string or '').strip()

    def _get_title(self, soup):
        return soup.find('a').string.strip()

    def _get_type(self, soup):
        if soup.find(string=re.compile(r'Directors?:')):
            return utils.ReleaseType.movie
        else:
            return utils.ReleaseType.series

    def _get_url(self, soup):
        id = self._get_id(soup)
        return f'{ImdbApi._url_base}/title/{id}'

    def _get_year(self, soup):
        try:
            year = soup.find(class_='lister-item-year').string or ''
        except AttributeError:
            return ''
        # Year may be preceded by roman number
        year = re.sub(r'\([IVXLCDM]+\)\s*', '', year)
        # Remove parentheses
        year = year.strip('()')
        # Possible formats:
        # - YYYY
        # - YYYY–YYYY  ("–" is NOT "U+002D / HYPHEN-MINUS" but "U+2013 / EN DASH")
        # - YYYY–
        try:
            return str(int(year[:4]))
        except (ValueError, TypeError):
            return ''


class _ImdbPie:
    def __init__(self):
        self._imdbpie = imdbpie.Imdb()
        self._request_lock = collections.defaultdict(lambda: asyncio.Lock())

    def _sync_request(self, method, id):
        # https://github.com/richardARPANET/imdb-pie/blob/master/CLIENT.rst#available-methods
        return getattr(self._imdbpie, f'get_{method}')(id)

    async def _async_request(self, method, id):
        wrapped = functools.partial(self._sync_request, method, id)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, wrapped)

    async def get(self, id, key='title'):
        # By using one Lock per requested information, we can savely call this
        # method multiple times concurrently without downloading the same data
        # more than once.
        request_lock_key = (id, key, builtins.id(asyncio.get_event_loop()))
        async with self._request_lock[request_lock_key]:
            cache_file = os.path.join(utils.fs.tmpdir(), f'imdb.{id}.{key}.json')

            # Try to read info from cache
            try:
                with open(cache_file, 'r') as f:
                    return json.loads(f.read())
            except (OSError, ValueError):
                pass

            # Make API request and return empty dict on failure
            try:
                info = await self._async_request(key, id)
            except (LookupError, imdbpie.exceptions.ImdbAPIError) as e:
                _log.debug('IMDb error: %r', e)
                info = {}

            # Cache info unless the request failed
            if info:
                try:
                    with open(cache_file, 'w') as f:
                        f.write(json.dumps(info))
                except OSError:
                    pass

            return info
