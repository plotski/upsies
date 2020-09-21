import collections

from async_lru import alru_cache

from . import _imdbpie

import logging  # isort:skip
_log = logging.getLogger(__name__)


@alru_cache(maxsize=None)
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


@alru_cache(maxsize=None)
async def year(id):
    """
    Return release year

    :param str id: IMDb ID (starts with "tt")
    """
    info = await _imdbpie.get_info(id, 'title')
    return str(info.get('base', {}).get('year', ''))


@alru_cache(maxsize=None)
async def title_original(id):
    """
    Return original title (e.g. non-English) or empty string

    :param str id: IMDb ID (starts with "tt")
    """
    info = await _imdbpie.get_info(id, 'title_versions')
    return info.get('originalTitle', '')


@alru_cache(maxsize=None)
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

    # US titles seem to be the most common
    priorities = (
        ('US', 'en'),
        ('XWW', 'en'),  # World-wide
        ('US', ''),
        ('', 'en'),
    )

    # Find English US title (US titles can also be Spanish)
    for key in priorities:
        if key in titles:
            if titles[key] != original_title:
                _log.debug('Found english title: %s: %r', key, titles[key])
                return titles[key]

    return ''
