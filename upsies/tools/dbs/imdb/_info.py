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

    def get_region_title(region):
        for title in info.get('alternateTitles', ()):
            if title.get('region') == region:
                if title.get('language', '').casefold() == 'en' or \
                   title.get('region', '').casefold() == 'us':
                    return title.get('title')

    original_title = await title_original(id)

    title = get_region_title('XWW')
    if title and title != original_title:
        return title

    title = get_region_title('US')
    if title and title != original_title:
        return title

    return ''
