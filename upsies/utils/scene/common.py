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
