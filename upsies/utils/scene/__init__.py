"""
Scene release search and verification
"""

import asyncio
import re

from ... import errors, utils
from .. import fs, subclasses, submodules
from ..types import ReleaseType, SceneCheckResult
from . import predb, srrdb
from .base import SceneDbApiBase
from .common import SceneQuery, assert_not_abbreviated_filename

import logging  # isort:skip
_log = logging.getLogger(__name__)

_PREDB = predb.PreDbApi()
_SRRDB = srrdb.SrrDbApi()

_NEEDED_MOVIE_KEYS = ('title', 'year', 'resolution', 'source', 'video_codec', 'group')
_NEEDED_SERIES_KEYS = ('title', 'episodes', 'resolution', 'source', 'video_codec', 'group')


def scenedbs():
    """Return list of :class:`.SceneDbApiBase` subclasses"""
    return subclasses(SceneDbApiBase, submodules(__package__))


def scenedb(name, **kwargs):
    """
    Create :class:`.SceneDbApiBase` instance

    :param str name: Name of the scene release database. A subclass of
        :class:`.SceneDbApiBase` with the same :attr:`~.SceneDbApiBase.name` must
        exist in one of this package's submodules.
    :param kwargs: All keyword arguments are passed to the subclass specified by
        `name`

    :raise ValueError: if no matching subclass can be found

    :return: :class:`.ClientApiBase` instance
    """
    for scenedb in scenedbs():
        if scenedb.name == name:
            return scenedb(**kwargs)
    raise ValueError(f'Unsupported scene release database: {name}')


async def search(*args, **kwargs):
    """Search with the recommended :class:`~.SceneDbApiBase` subclass"""
    return await _PREDB.search(*args, **kwargs)


async def is_scene_release(release):
    """
    Check if `release` is a scene release or not

    :param release: Release name, path to release,
        :class:`~.release.ReleaseName` or :class:`~.release.ReleaseInfo`
        instance or any :class:`dict`-like object with the same keys

    :return: :class:`~.types.SceneCheckResult`
    """
    if isinstance(release, str):
        release = utils.release.ReleaseInfo(release)

    # NOTE: Simply searching for the group does not work because some scene
    #       groups make non-scene releases and vice versa.
    #       Examples:
    #         - Prospect.2018.720p.BluRay.DD5.1.x264-LoRD
    #         - How.The.Grinch.Stole.Christmas.2000.720p.BluRay.DTS.x264-EbP
    query = SceneQuery.from_release(release)
    results = await _PREDB.search(query)
    if results:
        # Do we have enough information to find a single release?
        if release['type'] is ReleaseType.movie:
            needed_keys = _NEEDED_MOVIE_KEYS
        elif release['type'] in (ReleaseType.season, ReleaseType.episode):
            needed_keys = _NEEDED_SERIES_KEYS
        else:
            # If we don't even know the type, we certainly don't have enough
            # information to pin down a release.
            return SceneCheckResult.unknown

        if not all(release[k] for k in needed_keys):
            return SceneCheckResult.unknown
        else:
            return SceneCheckResult.true

    # If this is a file like "abd-mother.mkv" without a properly named parent
    # directory and we didn't find it above, it's possibly a scene release, but
    # we can't be sure.
    try:
        assert_not_abbreviated_filename(release.path)
    except errors.SceneError:
        return SceneCheckResult.unknown

    return SceneCheckResult.false
