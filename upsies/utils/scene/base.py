"""
Abstract base class for scene release databases
"""

import abc

from ... import errors, utils
from ..types import ReleaseType, SceneCheckResult
from .common import SceneQuery, assert_not_abbreviated_filename

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SceneDbApiBase(abc.ABC):
    """Base class for scene release database APIs"""

    @property
    @abc.abstractmethod
    def name(self):
        """Unique name of the scene release database"""

    @property
    @abc.abstractmethod
    def label(self):
        """User-facing name of the scene release database"""

    async def search(self, query, cache=True):
        """
        Search for scene release

        :param SceneQuery query: Search query
        :param bool cache: Whether to use cached request response

        :return: :class:`list` of release names as :class:`str`

        :raise RequestError: if the search request fails
        """
        return await query.search(self._search, cache=cache)

    @abc.abstractmethod
    async def _search(self, keywords, group=None, cache=True):
        pass

    _needed_movie_keys = ('title', 'year', 'resolution', 'source', 'video_codec', 'group')
    _needed_series_keys = ('title', 'episodes', 'resolution', 'source', 'video_codec', 'group')

    async def is_scene_release(self, release):
        """
        Check if `release` is a scene release or not

        :param release: Release name, path to release,
            :class:`~.release.ReleaseName` or :class:`~.release.ReleaseInfo`
            instance or any :class:`dict`-like object with the same keys

        :return: :class:`~.types.SceneCheckResult`
        """
        if isinstance(release, str):
            release = utils.release.ReleaseInfo(release)

        # IMPORTANT: Simply searching for the group does not work because some
        #            scene groups make non-scene releases and vice versa.
        #            Examples:
        #            - Prospect.2018.720p.BluRay.DD5.1.x264-LoRD
        #            - How.The.Grinch.Stole.Christmas.2000.720p.BluRay.DTS.x264-EbP
        query = SceneQuery.from_release(release)
        results = await self.search(query)
        if results:
            # Do we have enough information to find a single release?
            if release['type'] is ReleaseType.movie:
                needed_keys = self._needed_movie_keys
            elif release['type'] in (ReleaseType.season, ReleaseType.episode):
                needed_keys = self._needed_series_keys
            else:
                # If we don't even know the type, we certainly don't have enough
                # information to pin down a release.
                return SceneCheckResult.unknown

            if not all(release[k] for k in needed_keys):
                return SceneCheckResult.unknown
            else:
                return SceneCheckResult.true

        # If this is a file like "abd-mother.mkv" without a properly named
        # parent directory and we didn't find it above, it's possibly a scene
        # release, but we can't be sure.
        try:
            assert_not_abbreviated_filename(release.path)
        except errors.SceneError as e:
            return SceneCheckResult.unknown

        return SceneCheckResult.false
