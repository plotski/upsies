"""
Abstract base class for scene release databases
"""

import abc

from ... import errors
from .. import release as _release

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

    async def search(self, *query, group=None, cache=True):
        """
        Search for scene release

        :param query: Search keywords
        :param group: Release group name or `None`

        :return: :class:`list` of release names as :class:`str`
        """
        query = self._normalize_query(query)
        try:
            results = await self._search(query=query, group=group, cache=cache)
        except errors.RequestError as e:
            raise errors.SceneError(e)
        return self._normalize_results(results)

    @abc.abstractmethod
    async def _search(self, query, group=None, cache=True):
        pass

    def _normalize_query(self, query):
        """Turn sequence of sequences of space-separated words into list of words"""
        return [phrase
                for search_phrases in query
                for phrase in str(search_phrases).split()]

    def _normalize_results(self, results):
        """Return sorted list of sequence of search results"""
        return sorted(results, key=str.casefold)

    async def is_scene_group(self, group):
        """Whether `group` is a scene group"""
        return bool(await self.search(group=str(group)))

    async def is_scene_release(self, release):
        """
        Check if `release` is a scene release or not

        :param release: Release name or path to release content

        :return: `True`, `False` or `None` (unknown)
        """
        results = await self._search_with_series_info(release)
        if results:
            if self._release_is_in_results(release, results):
                return True

        # If we search for season pack but single episodes were released,
        # search without "S[0-9]+" to find the episode releases.
        elif release['type'] is _release.ReleaseType.season:
            results = await self._search_without_series_info(release)
            if results:
                if self._release_is_in_results(release, results):
                    return True

        # If this is a file like "abd-mother.mkv" without a properly named
        # parent directory, it's probably a scene release, but we can't say for
        # sure.
        from . import is_abbreviated_filename
        if is_abbreviated_filename(release.path):
            return None

        return False

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
        query = [x for x in (release['title'],
                             release['year'],
                             release.season_and_episode,
                             release['resolution'],
                             release['source'],
                             release['video_codec'])
                 if x]
        return await self.search(*query, group=release['group'])

    async def _search_without_series_info(self, release):
        query = [x for x in (release['title'],
                             release['year'],
                             release['resolution'],
                             release['source'],
                             release['video_codec'])
                 if x]
        return await self.search(*query, group=release['group'])
