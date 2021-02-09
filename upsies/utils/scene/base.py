"""
Abstract base class for scene release databases
"""

import abc

from ... import errors
from ..types import SceneCheckResult
from .common import SceneQuery, assert_not_abbreviated_filename


import logging  # isort:skip
_log = logging.getLogger(__name__)


class SceneDbApiBase(abc.ABC):
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

    async def is_scene_release(self, release):
        """
        Check if `release` is a scene release or not

        :param release: :class:`~.release.ReleaseName` or
            :class:`~.release.ReleaseInfo` instance or any :class:`dict`-like
            object with the expected keys.

        :return: :class:`~.types.SceneCheckResult`
        """
        # IMPORTANT: Simply searching for the group does not work because some
        #            scene groups make non-scene releases and vice versa.
        #            Examples:
        #            - Prospect.2018.720p.BluRay.DD5.1.x264-LoRD
        #            - How.The.Grinch.Stole.Christmas.2000.720p.BluRay.DTS.x264-EbP
        results = await self.search(SceneQuery.from_release(release))
        if results:
            return SceneCheckResult.true

        # If this is a file like "abd-mother.mkv" without a properly named
        # parent directory and we didn't find it above, it's possibly a scene
        # release, but we can't be sure.
        try:
            assert_not_abbreviated_filename(release.path)
        except errors.SceneError:
            return SceneCheckResult.unknown

        return SceneCheckResult.false
