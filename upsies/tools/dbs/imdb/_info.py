import collections
import string

from . import _imdbpie

import logging  # isort:skip
_log = logging.getLogger(__name__)


async def summary(id):
    """
    Get summary for movie or series

    :param str id: IMDb ID (starts with "tt")
    """
    info = await _imdbpie.get_info(id)
    try:
        return info['plot']['outline']['text']

    except KeyError:
        try:
            return info['plot']['summaries'][0]['text']
        except (KeyError, IndexError):
            pass
    return ''


async def year(id):
    """
    Return release year

    :param str id: IMDb ID (starts with "tt")
    """
    info = await _imdbpie.get_info(id, 'title')
    return str(info.get('base', {}).get('year', ''))


async def title_original(id):
    """
    Return original title (e.g. non-English) or empty string

    :param str id: IMDb ID (starts with "tt")
    """
    info = await _imdbpie.get_info(id, 'title_versions')
    return info.get('originalTitle', '')


async def title_english(id):
    """
    Return English title if it differs from original title

    :param str id: IMDb ID (starts with "tt")
    """
    info = await _imdbpie.get_info(id, 'title_versions')
    # Only consider titles with "imdbDisplay" type
    display_titles = [i for i in info.get('alternateTitles', ())
                      if 'imdbDisplay' in i.get('types', '')]
    titles = collections.defaultdict(lambda: [])

    # Map titles to region and language.
    # Both region and language may not exist or be undefined.
    # Ensure regions are upper case and languages are lower case.
    for i in display_titles:
        key = (i.get('region', '').upper(),
               i.get('language', '').lower())
        titles[key] = i['title']

    original_title = await title_original(id)
    _log.debug('Original title: %r', original_title)

    priorities = (
        ('US', 'en'),   # US titles seem to be the most commonly used
        ('XWW', 'en'),  # World-wide
        ('US', ''),
        ('', 'en'),
    )

    # Find English US title (US titles can also be Spanish)
    for key in priorities:
        if key in titles:
            if _normalize_title(titles[key]) != _normalize_title(original_title):
                _log.debug('English title: %s: %r', key, titles[key])
                return titles[key]

    return ''

def _normalize_title(title):
    """Return casefolded `title` with any punctuation removed"""
    trans = title.maketrans('', '', string.punctuation)
    return title.translate(trans).casefold()


async def type(id):
    """
    Get type: "movie", "season" "episode" or ""

    :param str id: IMDb ID (starts with "tt")
    """
    info = await _imdbpie.get_info(id)
    title_type = info.get('base', {}).get('titleType', '').casefold()
    if 'movie' in title_type:
        return 'movie'
    elif 'series' in title_type:
        return 'season'
    elif 'episode' in title_type:
        return 'episode'
    else:
        return ''


async def country(id):
    """
    Get country name

    :param str id: IMDb ID (starts with "tt")
    """
    from ....utils import country
    info = await _imdbpie.get_info(id, 'title_versions')
    codes = info.get('origins', '')  # Two-letter code (ISO 3166-1 alpha-2)
    if codes:
        return country.iso3166_alpha2_name.get(codes[0], '')
    else:
        return ''
