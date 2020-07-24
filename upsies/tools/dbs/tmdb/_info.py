from async_lru import alru_cache
from bs4 import BeautifulSoup

from .... import errors
from ....utils import http
from . import _url_base

import logging  # isort:skip
_log = logging.getLogger(__name__)


@alru_cache(maxsize=None)
async def summary(id):
    """
    Get summary for movie or series

    :param str id: TMDb ID: ["movie" or "tv"]/<number>
    """
    try:
        html = await http.get(f'{_url_base}/{id}', cache=True)
    except errors.RequestError:
        return ''

    soup = BeautifulSoup(html, features='html.parser')
    overview = ''.join(soup.find('div', class_='overview').stripped_strings)
    if overview == 'No overview found.':
        overview = ''
    return overview


@alru_cache(maxsize=None)
async def year(id):
    """
    Return release year

    :param str id: TMDb ID: ["movie" or "tv"]/<number>
    """
    try:
        html = await http.get(f'{_url_base}/{id}', cache=True)
    except errors.RequestError:
        return ''

    soup = BeautifulSoup(html, features='html.parser')
    year = ''.join(soup.find(class_='release_date').stripped_strings).strip('()')
    _log.debug(year)
    if len(year) == 4 and year.isdigit():
        return year
    else:
        return ''


@alru_cache(maxsize=None)
async def title_original(id):
    """
    Return original title (e.g. non-English) or empty string

    NOTE: There currently is no way to get this information and the returned
          string is always empty.

    :param str id: TMDb ID: ["movie" or "tv"]/<number>
    """
    return ''


@alru_cache(maxsize=None)
async def title_english(id):
    """
    Return English title if it differs from original title

    NOTE: There currently is no way to get this information and the returned
          string is always empty.

    :param str id: TMDb ID: ["movie" or "tv"]/<number>
    """
    return ''


@alru_cache(maxsize=None)
async def keywords(id):
    """
    Get list of keywords, e.g. genres for movie or series

    :param str id: TMDb ID: ["movie" or "tv"]/<number>
    """
    try:
        html = await http.get(f'{_url_base}/{id}', cache=True)
    except errors.RequestError:
        return ''

    soup = BeautifulSoup(html, features='html.parser')
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


@alru_cache(maxsize=None)
async def cast(id):
    """
    Get list of names of cast members

    :param str id: TMDb ID: ["movie" or "tv"]/<number>
    """
    try:
        html = await http.get(f'{_url_base}/{id}', cache=True)
    except errors.RequestError:
        return ''

    soup = BeautifulSoup(html, features='html.parser')
    cards = soup.select('.people > .card')
    cast = []
    for card in cards:
        for link in card.find_all('a'):
            strings = list(link.stripped_strings)
            if strings:
                cast.append(strings[0])
    return cast
