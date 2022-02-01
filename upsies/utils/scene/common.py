"""
Classes and functions that are not specific to
:class:`~.base.SceneDbApiBase` subclasses
"""

import re

from .. import release
from ..types import ReleaseType

_needed_movie_keys = ('title', 'year', 'resolution', 'source', 'video_codec', 'group')
_needed_series_keys = ('title', 'episodes', 'resolution', 'source', 'video_codec', 'group')


def get_needed_keys(release_info):
    """
    Return needed :class:`~.release.ReleaseInfo` keys to identify release

    :param release_info: :class:`~.release.ReleaseInfo` instance or any
        :class:`dict`-like object with the keys ``type`` and ``source``

    :return: Sequence of required keys or empty sequence if `release_info`
        doesn't contain a ``type``
    """
    if release_info['type'] is ReleaseType.movie:
        needed_keys = _needed_movie_keys
    elif release_info['type'] in (ReleaseType.season, ReleaseType.episode):
        needed_keys = _needed_series_keys
    else:
        # If we don't even know the type, we certainly don't have enough
        # information to pin down a release.
        return ()

    # DVDRips typically don't include resolution in release name
    if release_info['source'] == 'DVDRip':
        needed_keys = list(needed_keys)
        needed_keys.remove('resolution')

    return tuple(needed_keys)


def get_season_pack_name(release_name):
    """Remove episode information (e.g. "E03") from `release_name`"""
    # Remove episode(s) from release name to create season pack name
    season_pack = re.sub(
        (
            r'\b'
            rf'(S\d{{2,}})'
            rf'(?:{release.DELIM}*E\d{{2,}})+'
            r'\b'
        ),
        r'\1',
        release_name,
    )

    # Remove episode title
    release_info = release.ReleaseInfo(release_name)
    if release_info['episode_title']:
        # Escape special characters in each word and
        # join words with "space or period" regex
        episode_title_regex = rf'{release.DELIM}+'.join(
            re.escape(word)
            for word in release_info['episode_title'].split()
        )
        season_pack = re.sub(rf'\b{episode_title_regex}\W', '', season_pack)

    return season_pack
