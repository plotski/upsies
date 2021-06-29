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

    default_config = {}

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

        if query.id:
            _log.debug('Getting ID: %r', query.id)
            return [_ImdbSearchResult(
                imdb_api=self,
                cast=functools.partial(self.cast, query.id),
                countries=functools.partial(self.countries, query.id),
                directors=functools.partial(self.directors, query.id),
                genres=functools.partial(self.genres, query.id),
                id=query.id,
                summary=functools.partial(self.summary, query.id),
                title=await self.title_english(query.id),
                title_english=functools.partial(self.title_english, query.id),
                title_original=functools.partial(self.title_original, query.id),
                type=await self.type(query.id),
                url=await self.url(query.id),
                year=await self.year(query.id),
            )]

        elif not query.title:
            return []

        else:
            path = 'search/title/'
            params = {'title': query.title_normalized if not query.id else query.id}
            _log.debug('PARAMS: %r', params)
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
        cast = []
        if id:
            soup = await self._get_soup(f'title/{id}')
            # New website
            cast_tag = soup.find(class_='title-cast__grid')
            if cast_tag is None:
                # Old website
                cast_tag = soup.find(class_='cast_list')
            if cast_tag:
                cast.extend(self._get_persons(cast_tag))
        return tuple(cast)

    _country_translation = {
        'United States': 'USA',
        'United Kingdom': 'UK',
    }

    async def countries(self, id):
        countries = []
        if id:
            soup = await self._get_soup(f'title/{id}')
            a_tags = soup.find_all(href=re.compile(r'/search/title.*?country_of_origin='))
            for a_tag in a_tags:
                country = ''.join(a_tag.stripped_strings)
                countries.append(self._country_translation.get(country, country))
        return tuple(countries)

    _creators_label_regex = re.compile('^Creators?:?$')

    async def creators(self, id):
        if id:
            soup = await self._get_soup(f'title/{id}')
            # Old website design
            credits_tags = soup.find_all(class_='credit_summary_item')
            if not credits_tags:
                # New website design
                credits_tags = soup.find_all(class_='ipc-metadata-list__item')
            for tag in credits_tags:
                if any(self._creators_label_regex.search(string)
                       for string in tag.stripped_strings):
                    return self._get_persons(tag)
        return ()

    _directors_label_regex = re.compile('^Directors?:?$')

    async def directors(self, id):
        if id:
            soup = await self._get_soup(f'title/{id}')
            # Old website design
            credits_tags = soup.find_all(class_='credit_summary_item')
            if not credits_tags:
                # New website design
                credits_tags = soup.find_all(class_='ipc-metadata-list__item')
            for tag in credits_tags:
                if any(self._directors_label_regex.search(string)
                       for string in tag.stripped_strings):
                    return self._get_persons(tag)
        return ()

    async def genres(self, id):
        if id:
            soup = await self._get_soup(f'title/{id}')
            # Old website design
            parent_tag = soup.find(class_='subtext')
            if not parent_tag:
                # New website design
                parent_tag = soup.find(class_=re.compile(r'^GenresAndPlot__ContentParent'))
            if parent_tag:
                genre_links = parent_tag.find_all('a', href=re.compile(r'/search/title\?.*genres='))
                return tuple(link.string.lower().strip() for link in genre_links)
        return ()

    async def poster_url(self, id):
        if id:
            soup = await self._get_soup(f'title/{id}')
            a_tag = soup.find(href=re.compile(r'/title/tt\d+/mediaviewer/'))
            if a_tag:
                soup = await self._get_soup(a_tag['href'])
                img_tags = [
                    tag
                    for tag in soup.find_all('img', class_=re.compile(r'^MediaViewerImagestyles__PortraitImage'))
                    if 'peek' not in tag['class']
                ]
                if img_tags:
                    url = img_tags[0].get('src')
                    if url:
                        return url
        return ''

    rating_min = 0.0
    rating_max = 10.0

    async def rating(self, id):
        if id:
            soup = await self._get_soup(f'title/{id}')
            rating_tag = soup.find(itemprop='ratingValue')
            if not rating_tag:
                rating_tag = soup.find(class_=re.compile(r'^AggregateRatingButton__RatingScore.*'))
            if rating_tag:
                try:
                    return float(rating_tag.string)
                except (ValueError, TypeError):
                    pass
        return None

    async def summary(self, id):
        if id:
            soup = await self._get_soup(f'title/{id}')

            # Get summary from the top
            candidates = (
                # Old website design
                soup.find(class_='summary_text'),
                # New website design
                soup.find(class_=re.compile(r'GenresAndPlot__TextContainerBreakpointXL.*')),
            )
            for tag in candidates:
                if tag:
                    string = ''.join(tag.stripped_strings).strip()
                    link_texts = ('See full summary»', 'Read all', 'Add a Plot»')
                    if all(not string.endswith(text) for text in link_texts):
                        return string

            # Get summary from the "Storyline" section (old website design)
            try:
                tag = soup.find(id='titleStoryLine').div.p.span
            except AttributeError:
                pass
            else:
                # Remove "Written by [Author]" signature
                return re.sub(r'\s*(?i:Written\s+by).*?$', '', ''.join(tag.strings)).strip()

            # Get summary from the "Storyline" section (new website design)
            try:
                tag = soup.find(class_=re.compile(r'^Storyline__StorylineWrapper.*')).div.div.div
            except AttributeError:
                pass
            else:
                # Remove "—[Author]" signature
                return re.sub(r'\s*—.*?$', '', ''.join(tag.strings)).strip()

        return ''

    async def title_english(self, id, allow_empty=True):
        if id:
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
        if id:
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
        return ''

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
        re.compile(r'^USA.*reissue'),
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
        if id:
            soup = await self._get_soup(f'title/{id}')

            # Old website design
            subtext_tag = soup.find(class_='subtext')
            if subtext_tag:
                # reversed() because interesting info is on the right side
                subtext = ' '.join(reversed(tuple(subtext_tag.stripped_strings))).lower()

            else:
                # New website design
                subtext_tag = soup.find(class_=re.compile(r'^TitleBlockMetaData__MetaDataList'))
                if subtext_tag:
                    subtext = ' '.join(subtext_tag.stripped_strings).lower()

            if subtext:
                if 'episode' in subtext:
                    return ReleaseType.episode
                elif 'tv series' in subtext:
                    return ReleaseType.season
                elif re.search(r'tv mini[- ]series', subtext):
                    return ReleaseType.season
                elif subtext.endswith('video') or subtext.startswith('video'):
                    return ReleaseType.movie
                elif 'tv movie' in subtext:
                    return ReleaseType.movie
                elif (
                    # Look for year (old website design)
                    re.search(r'^\d+ [a-z]+ \d{4}', subtext)
                    # Look for year (new website design)
                    or re.search(r'^\d{4}', subtext)
                ):
                    return ReleaseType.movie

        return ReleaseType.unknown

    async def url(self, id):
        if id:
            return f'{self._url_base.rstrip("/")}/title/{id}'
        return ''

    async def year(self, id):
        if id:
            soup = await self._get_soup(f'title/{id}')

            # Movies (old website design)
            year_tag = soup.find(id='titleYear')
            if year_tag:
                return ''.join(year_tag.stripped_strings).strip('()')

            # Series (old website design)
            subtext_tag = soup.find(class_='subtext')
            if subtext_tag:
                # reversed() because interesting info is on the right side
                subtext = ' '.join(reversed(tuple(subtext_tag.stripped_strings)))
            else:
                # Series (new website design)
                subtext_tag = soup.find(class_=re.compile(r'^TitleBlock__TitleMetaDataContainer'))
                if subtext_tag:
                    subtext = ' '.join(subtext_tag.stripped_strings)

            if subtext:
                match = re.search(r'\b(\d{4})\b', subtext)
                if match:
                    return match.group(1)

        return ''


class _ImdbSearchResult(common.SearchResult):
    def __init__(self, *, imdb_api, soup=None, cast=None, countries=None,
                 directors=None, id=None, genres=None, summary=None, title=None,
                 title_english=None, title_original=None, type=None, url=None,
                 year=None):
        soup = soup or html.parse('')
        id = id or self._get_id(soup)
        return super().__init__(
            cast=cast or self._get_cast(soup),
            countries=countries or functools.partial(imdb_api.countries, id),
            directors=directors or self._get_directors(soup),
            genres=genres or self._get_genres(soup),
            id=id or self._get_id(soup),
            summary=summary or self._get_summary(soup),
            title=title or self._get_title(soup),
            title_english=title_english or functools.partial(imdb_api.title_english, id),
            title_original=title_original or functools.partial(imdb_api.title_original, id),
            type=type or self._get_type(soup),
            url=url or self._get_url(soup),
            year=year or self._get_year(soup),
        )

    def _get_cast(self, soup):
        people = soup.find(string=re.compile(r'Stars?.*'))
        if people:
            names = tuple(name.string.strip() for name in people.parent.find_all('a'))
            return names[1:]
        else:
            return ()

    def _get_directors(self, soup):
        people = soup.find(string=re.compile(r'Director?.*'))
        if people:
            director = people.parent.find('a')
            if director:
                return (director.string.strip(),)
        else:
            return ()

    def _get_id(self, soup):
        a_tag = soup.find('a')
        if a_tag:
            href = a_tag.get('href')
            return re.sub(r'^.*/([t0-9]+)/.*$', r'\1', href)
        return ''

    def _get_genres(self, soup):
        try:
            genres = soup.find(class_='genre').string.strip()
        except AttributeError:
            genres = ''
        if genres:
            return tuple(g.strip().casefold() for g in genres.split(','))
        else:
            return ()

    def _get_summary(self, soup):
        summary = ''

        tags = soup.find_all(class_='text-muted')
        if len(tags) >= 3:
            strings = tuple(tags[2].strings)
            if strings and 'Add a Plot' not in strings:
                summary = (''.join(strings) or '').strip()

        # Look for "See full summary" link. Preceding text is summary.
        if not summary:
            summary_link = soup.find('a', text=re.compile(r'(?i:full\s+summary)'))
            if summary_link:
                summary_tag = summary_link.parent
                if summary_tag:
                    summary = ''.join(summary_tag.strings)

        summary = re.sub(r'(?i:see full summary).*', '', summary).strip()
        summary = re.sub(r'\s*\.\.\.\s*$', '…', summary)

        return summary

    def _get_title(self, soup):
        a_tag = soup.find('a')
        if a_tag:
            return a_tag.string.strip()
        return ''

    def _get_type(self, soup):
        if soup.find(string=re.compile(r'Directors?:')):
            return ReleaseType.movie
        else:
            return ReleaseType.series

    def _get_url(self, soup):
        id = self._get_id(soup)
        if id:
            return f'{ImdbApi._url_base}/title/{id}'
        return ''

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
