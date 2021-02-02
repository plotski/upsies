"""
Abstract base class for scene release databases
"""

import abc

from ... import errors
from .. import release as _release
from .common import SceneQuery

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
        """
        try:
            results = await self._search(
                query=query.keywords,
                group=query.group,
                cache=cache,
            )
        except errors.RequestError as e:
            raise errors.SceneError(e)
        return sorted(results, key=str.casefold)

    @abc.abstractmethod
    async def _search(self, query, group=None, cache=True):
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
        results = await self._search_with_series_info(release)
        if results:
            if self._release_is_in_results(release, results):
                return SceneCheckResult.true

        # If we search for season pack but single episodes were released,
        # search without "S[0-9]+" to find the episode releases.
        elif release['type'] is _release.ReleaseType.season:
            results = await self._search_without_series_info(release)
            if results:
                if self._release_is_in_results(release, results):
                    return SceneCheckResult.true

        # If this is a file like "abd-mother.mkv" without a properly named
        # parent directory, it's probably a scene release, but we can't say for
        # sure.
        from . import is_abbreviated_filename
        if is_abbreviated_filename(release.path):
            return SceneCheckResult.unknown

        return SceneCheckResult.false

    def _release_is_in_results(self, release, results):
        results = [_release.ReleaseInfo(r) for r in results]

        def releases_equal(r1, r2, cmp_episodes=True):
            # Compare only some information in case `release` comes from a
            # renamed release. We don't validate the release name here, only
            # check if the typical scene release information matches our input.
            if cmp_episodes:
                keys = ('title', 'year', 'season', 'episode', 'resolution',
                        'source', 'video_codec', 'group')
            else:
                keys = ('title', 'year', 'season', 'resolution',
                        'source', 'video_codec', 'group')
            for key in keys:
                if r1[key].casefold() != r2[key].casefold():
                    _log.debug('%s: Not a scene release because %r != %r',
                               release.path, r1[key], r2[key])
                    return False
            return True

        # Try to find the exact release
        for result in results:
            if releases_equal(release, result, cmp_episodes=True):
                return True

        # If we can't find the exact release, we might be looking at a season
        # pack that was originally released as individual episodes. Searching
        # for "S04" doesn't yield any results for "S04E01/2/3/..." releases.
        if release['season'] and not release['episode']:
            for result in results:
                if releases_equal(release, result, cmp_episodes=False):
                    return True

        return False

    async def _search_with_series_info(self, release):
        query = SceneQuery(
            *(x for x in (release['title'],
                          release['year'],
                          release['season_and_episode'],
                          release['resolution'],
                          release['source'],
                          release['video_codec'])
              if x),
            group=release['group'],
        )
        _log.debug('Scene query: %r', query)
        return await self.search(query)

    async def _search_without_series_info(self, release):
        query = SceneQuery(
            *(x for x in (release['title'],
                          release['year'],
                          release['resolution'],
                          release['source'],
                          release['video_codec'])
              if x),
            group=release['group'],
        )
        _log.debug('Scene query: %r', query)
        return await self.search(query)
