import functools
import re
import time

from ....utils import LazyModule, http
from .. import _common
from . import _info, _url_base

import logging  # isort:skip
_log = logging.getLogger(__name__)

bs4 = LazyModule(module='bs4', namespace=globals())


class ImdbSearchResult(_common.SearchResult):
    @property
    def summary(self):
        return functools.partial(_info.summary, self.id)

    @property
    def title_original(self):
        return functools.partial(_info.title_original, self.id)

    @property
    def title_english(self):
        return functools.partial(_info.title_english, self.id)


# Scraping IMDb's advanced search website is slower but let's us specify type
# and year.

_title_types = {
    'movie' : 'feature,tv_movie,documentary,video',
    'series' : 'tv_series,tv_miniseries',
    'episode' : 'tv_episode',
}
_title_types[None] = ','.join(_title_types.values())


async def search(title, type=None, year=None):
    """
    Search IMDb

    :param str title: Name of movie or series
    :param str type: "movie" "series" or "episode"
    :param year: Year of release
    :type year: str or int

    :raise RequestError: if the search request fails

    :return: Sequence of SearchResult objects
    """
    if type not in _title_types:
        raise ValueError(f'Unknown type: {type}')

    title = title.strip()
    _log.debug('Searching IMDb for %r, type=%r, year=%r', title, type, year)
    if not title:
        return ()

    url = f'{_url_base}/search/title/'
    params = {
        'title': title,
        'title_type': _title_types[type],
    }
    _log.debug('params: %r', params)

    if year is not None:
        params['release_date'] = f'{year}-01-01,{year}-12-31'

    html = await http.get(url, params=params, cache=True)
    soup = bs4.BeautifulSoup(html, features='html.parser')

    start = time.monotonic()
    items = soup.find_all('div', class_='lister-item-content')
    results = tuple(_make_result(item) for item in items)
    _log.debug('Parsed %r search results in %.3fms', len(results), (time.monotonic() - start) * 1000)
    return results

def _make_result(item):
    return ImdbSearchResult(
        id=_find_id(item),
        url=_find_url(item),
        type=_find_type(item),
        title=_find_title(item),
        year=_find_year(item),
        keywords=_find_keywords(item),
        cast=_find_cast(item),
    )

def _find_id(soup):
    href = soup.find('a').get('href')
    return re.sub(r'^.*/([t0-9]+)/.*$', r'\1', href)

def _find_url(soup):
    href = soup.find('a').get('href')
    if href.startswith('http'):
        return href
    elif href.startswith('/'):
        return f'{_url_base}{href}'
    else:
        return f'{_url_base}/{href}'

def _find_type(soup):
    if soup.find(string=re.compile(r'Directors?:')):
        return 'movie'
    else:
        return 'series'

def _find_title(soup):
    return soup.find('a').string.strip()

def _find_year(soup):
    try:
        year = soup.find(class_='lister-item-year').string or ''
    except AttributeError:
        return ''
    # Year may be preceded with "(I[II...])".
    year = re.sub(r'\(I+\)\s*', '', year)
    # Remove parentheses
    year = year.strip('()')
    # Possible formats:
    # - YYYY
    # - YYYY–YYYY  ("–" is NOT "-", i.e. "\u2D")
    # - YYYY–
    try:
        return str(int(year[:4]))
    except (ValueError, TypeError):
        return ''

def _find_keywords(soup):
    try:
        keywords = soup.find(class_='genre').string.strip()
    except AttributeError:
        keywords = ''
    return [g.strip().casefold() for g in keywords.split(',')]

def _find_cast(soup):
    names = soup.find(string=re.compile(r'Stars?.*'))
    if names:
        # First link is director
        return [name.string.strip() for name in names.parent.find_all('a')[1:]]
    else:
        return []
