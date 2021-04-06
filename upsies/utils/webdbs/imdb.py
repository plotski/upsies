"""
API for imdb.com
"""

import functools
import re
import string

from .. import html, http
from ..types import ReleaseType
from . import common
from .base import WebDbApiBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ImdbApi(WebDbApiBase):
    """API for imdb.com"""

    name = 'imdb'
    label = 'IMDb'
    _url_base = 'https://imdb.com'

    _soup_cache = {}

    async def _get_soup(self, path, params={}):
        cache_id = (path, tuple(sorted(params.items())))
        if cache_id in self._soup_cache:
            return self._soup_cache[cache_id]
        text = await http.get(
            url=f'{self._url_base}/{path}',
            params=params,
            cache=True,
        )
        self._soup_cache[cache_id] = html.parse(text)
        return self._soup_cache[cache_id]

    _title_types = {
        ReleaseType.movie: 'feature,tv_movie,documentary,short,video,tv_short',
        ReleaseType.season: 'tv_series,tv_miniseries',
        # Searching for single episodes is currently not supported
        ReleaseType.episode: 'tv_series,tv_miniseries',
    }

    async def search(self, query):
        _log.debug('Searching IMDb for %s', query)
        if not query.title:
            return []

        path = 'search/title/'
        params = {'title': query.title_normalized}
        if query.type is not ReleaseType.unknown:
            params['title_type'] = self._title_types[query.type]
        if query.year is not None:
            params['release_date'] = f'{query.year}-01-01,{query.year}-12-31'

        soup = await self._get_soup(path, params=params)
        items = soup.find_all('div', class_='lister-item-content')
        results = [_ImdbSearchResult(soup=item, imdb_api=self)
                   for item in items]
        return results

    _person_url_path_regex = re.compile(r'(/name/nm\d+)')

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
        soup = await self._get_soup(f'title/{id}')
        cast_tag = soup.find(class_='cast_list')
        cast = []
        tr_tags = cast_tag.find_all('tr')
        for tr_tag in tr_tags:
            cast.extend(self._get_persons(tr_tag))
        return tuple(cast)

    async def countries(self, id):
        soup = await self._get_soup(f'title/{id}')
        details_tag = soup.find(id='titleDetails')
        countries_tag = details_tag.find(string='Country:').parent.parent
        countries = []
        for country_tag in countries_tag.find_all('a'):
            countries.append(''.join(country_tag.stripped_strings))
        return tuple(countries)

    async def creators(self, id):
        soup = await self._get_soup(f'title/{id}')
        creators = []
        for tag in soup.find_all(class_='credit_summary_item'):
            strings = tuple(tag.stripped_strings)
            if 'Creator:' in strings or 'Creators:' in strings:
                creators.extend(self._get_persons(tag))
        return tuple(creators)

    async def directors(self, id):
        soup = await self._get_soup(f'title/{id}')
        directors = []
        for tag in soup.find_all(class_='credit_summary_item'):
            strings = tuple(tag.stripped_strings)
            if 'Director:' in strings or 'Directors:' in strings:
                directors.extend(self._get_persons(tag))
        return tuple(directors)

    async def keywords(self, id):
        soup = await self._get_soup(f'title/{id}')
        subtext_tag = soup.find(class_='subtext')
        if subtext_tag:
            genre_links = subtext_tag.find_all('a', href=re.compile(r'/search/title\?genres='))
            return tuple(
                link.string.lower().strip()
                for link in genre_links
            )
        return ()

    async def poster_url(self, id):
        soup = await self._get_soup(f'title/{id}')
        poster_tag = soup.find(class_='poster')
        if poster_tag:
            link_tag = poster_tag.find('a')
            if link_tag and link_tag.get('href'):
                soup = await self._get_soup(link_tag['href'])
                img_tags = [
                    tag
                    for tag in soup.find_all('img', class_=re.compile(r'^MediaViewerImagestyles__PortraitImage'))
                    if 'peek' not in tag['class']
                ]
                if img_tags:
                    url = img_tags[0].get('src')
                    if url:
                        return url

    rating_min = 0.0
    rating_max = 10.0

    async def rating(self, id):
        soup = await self._get_soup(f'title/{id}')
        rating_tag = soup.find(itemprop='ratingValue')
        if rating_tag:
            try:
                return float(rating_tag.string)
            except (ValueError, TypeError):
                pass

    async def summary(self, id):
        soup = await self._get_soup(f'title/{id}')
        storyline_tag = soup.find(id='titleStoryLine')
        try:
            summary_tag = storyline_tag.div.p.span
        except AttributeError:
            pass
        else:
            if summary_tag:
                return ''.join(summary_tag.strings).strip()
        return ''

    async def title_english(self, id, allow_empty=True):
        akas = await self._get_akas(id)
        original_title = akas.get('(original title)', '')
        for key, english_title in akas.items():
            for regex in self._english_akas_keys:
                if regex.search(key):
                    # _log.debug('Interesting English title: %r -> %r', key, english_title)
                    if not allow_empty:
                        # _log.debug('Forcing first match: %r', english_title)
                        return english_title
                    if not self._titles_are_similar(english_title, original_title):
                        # _log.debug('English title: %r', english_title)
                        # _log.debug('Original title: %r', original_title)
                        return english_title
                    # else:
                    #     _log.debug('Similar to original title %r: %r', original_title, english_title)
        return ''

    async def title_original(self, id):
        akas = await self._get_akas(id)
        original_title = akas.get('(original title)', '')
        english_title = await self.title_english(id, allow_empty=False)
        if original_title:
            if not self._titles_are_similar(original_title, english_title):
                # _log.debug('Original title: %r', original_title)
                # _log.debug('English title: %r', english_title)
                return original_title
            # else:
            #     _log.debug('Similar to English title %r: %r', english_title, original_title)
        else:
            # Default to getting title from link to main page
            # _log.debug('No original title in AKAs found')
            soup = await self._get_soup(f'title/{id}/releaseinfo')
            title_tag = soup.find(class_='subpage_title_block__right-column')
            if title_tag:
                a_tag = title_tag.find('a', href=re.compile(r'/title/tt'))
                if a_tag:
                    return a_tag.string

        _log.debug('Defaulting to English title: %r', english_title)
        return english_title

    def _titles_are_similar(self, a, b):
        """Whether normalized `a` contains normalized `b` or vice versa"""
        an = self._normalize_title(a)
        bn = self._normalize_title(b)
        return an and bn and (an in bn or bn in an)

    _normalize_title_translation = str.maketrans('', '', string.punctuation)

    def _normalize_title(self, title):
        """Return casefolded `title` without punctuation and deduplicated whitespace"""
        return ' '.join(title.translate(self._normalize_title_translation).casefold().split())

    _ignored_akas_keys = (
        re.compile(r'\(TV title\)$'),
        re.compile(r'\(alternative spelling\)$'),
        re.compile(r'\(dubbed version\)$'),
        re.compile(r'\(literal title\)$'),
        re.compile(r'\(original script title\)$'),
        re.compile(r'\(short title\)$'),
        re.compile(r'\(video box title\)$'),
        re.compile(r'\(working title\)$'),
    )
    _english_akas_keys = (
        re.compile(r'^USA.*English'),
        re.compile(r'^USA$'),
        re.compile(r'^World-wide.*English'),
    )

    async def _get_akas(self, id):
        soup = await self._get_soup(f'title/{id}/releaseinfo')
        akas = {}

        def is_item_key_class(class_):
            # Class may also be named "aka-item__name-empty"
            return class_ and class_.startswith('aka-item__name')

        for item in soup.find_all('tr', class_='aka-item'):
            key_tag = item.find('td', class_=is_item_key_class)
            key = ''.join(key_tag.stripped_strings).strip()

            title_tag = item.find('td', class_='aka-item__title')
            title = ''.join(title_tag.stripped_strings).strip()

            if title:
                if not any(regex.search(key) for regex in self._ignored_akas_keys):
                    akas[key] = title
            #     else:
            #         _log.debug('Ignoring AKA: %r -> %r', key, title)
            # else:
            #     _log.debug('Ignoring empty title: %r -> %r', key, title)

        return akas

    async def type(self, id):
        soup = await self._get_soup(f'title/{id}')
        subtext_tag = soup.find(class_='subtext')
        if subtext_tag:
            # reversed() because interesting info is on the right side
            subtexts = ''.join(subtext_tag.stripped_strings).lower().split('|')
            genres = [genre.string.lower() for genre in subtext_tag.find_all(
                'a', href=re.compile(r'/search/title\?genres='))]
            if 'episode' in subtexts[-1]:
                return ReleaseType.episode
            elif 'tv series' in subtexts[-1]:
                return ReleaseType.season
            elif 'tv mini-series' in subtexts[-1]:
                return ReleaseType.season
            elif 'tv short' in subtexts[-1]:
                return ReleaseType.movie
            elif 'short' in genres:
                return ReleaseType.movie
            elif 'video' in subtexts[-1].split(' '):
                return ReleaseType.movie
            elif 'tv movie' in subtexts[-1]:
                return ReleaseType.movie
            elif re.search(r'^\d+ [a-z]+ \d{4}', subtexts[-1]):
                return ReleaseType.movie
        return ReleaseType.unknown

    async def url(self, id):
        return f'{self._url_base.rstrip("/")}/title/{id}'

    async def year(self, id):
        soup = await self._get_soup(f'title/{id}')

        # Movies
        year_tag = soup.find(id='titleYear')
        if year_tag:
            return ''.join(year_tag.stripped_strings).strip('()')

        # Series
        subtext_tag = soup.find(class_='subtext')
        if subtext_tag:
            # reversed() because year is on the very right
            for tag in reversed(subtext_tag.find_all()):
                text = ''.join(tag.stripped_strings)
                # Looking for one of these:
                #   - "TV Mini-Series (<YEAR>)"
                #   - "TV Series (<YEAR>–<year>)" (the "–" is an EN DASH / U+2013)
                #   - "<day> <month> <YEAR>"
                match = re.search(r'\b(\d{4})\b', text)
                if match:
                    return match.group(1)

        return ''


class _ImdbSearchResult(common.SearchResult):
    def __init__(self, *, soup, imdb_api):
        id = self._get_id(soup)
        return super().__init__(
            cast=self._get_cast(soup),
            countries=functools.partial(imdb_api.countries, id),
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
            names = tuple(name.string.strip() for name in people.parent.find_all('a'))
            return names[1:]
        else:
            return ()

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
        return tuple(kw.strip().casefold() for kw in keywords.split(','))

    def _get_summary(self, soup):
        tags = soup.find_all(class_='text-muted')
        summary = (tags[2].string or '').strip()

        # Look for "See full summary" link. Preceding text is summary.
        if not summary:
            summary_link = soup.find('a', text=re.compile(r'(?i:full\s+summary)'))
            if summary_link:
                summary_tag = summary_link.parent
                if summary_tag:
                    summary = ''.join(summary_tag.strings)
                    summary = re.sub(r'See full summary.*', '', summary).strip()
        return summary

    def _get_title(self, soup):
        return soup.find('a').string.strip()

    def _get_type(self, soup):
        if soup.find(string=re.compile(r'Directors?:')):
            return ReleaseType.movie
        else:
            return ReleaseType.series

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
