import functools
import re

from ....utils import LazyModule, http
from .. import _common
from . import _info, _url_base

import logging  # isort:skip
_log = logging.getLogger(__name__)

bs4 = LazyModule(module='bs4', namespace=globals())


class TmdbSearchResult(_common.SearchResult):
    @property
    def summary(self):
        return functools.partial(_info.summary, self.id)

    @property
    def keywords(self):
        return functools.partial(_info.keywords, self.id)

    @property
    def cast(self):
        return functools.partial(_info.cast, self.id)


async def search(title, type=None, year=None):
    """
    Search for TMDb ID

    :param str title: Name of movie or series
    :param str type: "movie" "series" or "episode"
    :param year: Year of release
    :type year: str or int

    :raise RequestError: if the search request fails

    :return: Sequence of SearchResult objects
    """
    title = title.strip()
    _log.debug('Searching TMDb for %r, type=%r, year=%r', title, type, year)
    if not title:
        return ()

    query = title
    if year is not None:
        query += f' y:{year}'
    if type == 'movie':
        url = f'{_url_base}/search/movie'
    elif type == 'series':
        url = f'{_url_base}/search/tv'
    else:
        url = f'{_url_base}/search'
    params = {'query': query}

    html = await http.get(url, params=params, cache=True)
    soup = bs4.BeautifulSoup(html, features='html.parser')

    items = soup.find_all('div', class_='card')
    return tuple(_make_result(item) for item in items)

def _make_result(item):
    return TmdbSearchResult(
        id=_find_id(item),
        url=_find_url(item),
        type=_find_type(item),
        title=_find_title(item),
        year=_find_year(item),
    )

def _find_id(soup):
    href = soup.find('a', class_='result').get('href')
    return re.sub(r'^.*/((?:movie|tv)/[0-9]+).*?$', r'\1', href)

def _find_url(soup):
    href = soup.find('a', class_='result').get('href')
    if href.startswith('http'):
        return href
    elif href.startswith('/'):
        return f'{_url_base}{href}'
    else:
        return f'{_url_base}/{href}'

def _find_type(soup):
    href = soup.find('a', class_='result').get('href')
    tmdb_type = re.sub(r'(?:^|/)(\w+)/.*$', r'\1', href)
    if tmdb_type == 'movie':
        return 'movie'
    elif tmdb_type == 'tv':
        return 'series'
    else:
        return ''

def _find_title(soup):
    header = soup.select('.result > h2')
    if header:
        return header[0].string
    else:
        return ''

def _find_year(soup):
    release_date = soup.find(class_='release_date')
    if release_date:
        match = re.search(r'(\d{4})$', release_date.string)
        if match:
            return match.group(1)
    return ''
