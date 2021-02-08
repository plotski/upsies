"""
Classes and functions that are used by all :class:`~.base.SceneDbApiBase`
subclasses
"""

import os
import re

from ... import errors
from .. import LazyModule, release

import logging  # isort:skip
_log = logging.getLogger(__name__)

natsort = LazyModule(module='natsort', namespace=globals())


class SceneQuery:
    """
    Query for scene release databases

    :param keywords: Search keywords
    :param group: Release group name
    :param episodes: :class:`~.release.Episodes`-like mapping
    """

    def __init__(self, *keywords, group='', episodes={}):
        # Split each keyword
        self._keywords = tuple(k.strip() for kw in keywords
                               for k in str(kw).split()
                               if k.strip() and k.strip() != '-')
        self._group = str(group)
        self._episodes = episodes

    @classmethod
    def from_string(cls, string):
        """
        Create query from `string`

        :param string: Release name or path to release content

        `string` is passed to :class:`~.release.ReleaseInfo` and the result is
        passed to :meth:`from_release`.

        :raise SceneError: if :class:`~.release.ReleaseInfo` raises
            :class:`~.errors.ContentError`
        """
        try:
            return cls.from_release(release.ReleaseInfo(string, strict=True))
        except errors.ContentError as e:
            raise errors.SceneError(e)

    @classmethod
    def from_release(cls, release):
        """
        Create query from :class:`dict`-like object

        :param release: :class:`~.release.ReleaseName` or
            :class:`~.release.ReleaseInfo` instance or any :class:`dict`-like
            object with the keys ``title``, ``year``, ``episodes``,
            ``resolution``, ``source``, ``video_codec`` and ``group``.
        """
        info = dict(release)
        keywords = [info['title']]
        for key in ('year', 'episodes', 'resolution', 'source', 'video_codec'):
            if info.get(key):
                keywords.append(info[key])
        query = cls(
            *keywords,
            group=release.get('group', ''),
            episodes=info.get('episodes', {}),
        )
        _log.debug('SceneQuery from %r: %r', info, query)
        return query

    async def search(self, search_coro_func, cache=True):
        """
        Pre-process query and post-process results from `search_coro_func`

        :param search_coro_func: Coroutine function with the call signature
            `(keywords, group, cache)` that returns a sequence of release names
        :param bool cache: Whether to return cached results

        This is a wrapper function that exists to work around scene release
        databases not handling season/episode information inuitively.

        Any `keywords` that look like "S01", "S02E03", etc are removed in the
        search request.

        The search results are then filtered for the specific `episodes` given
        during instantiation and returned in natural sort order.
        """
        keywords = tuple(kw for kw in self.keywords
                         if not re.match(r'^(?i:[SE]\d+|)+$', kw))
        _log.debug('Searching for scene release: %r', keywords)
        try:
            results = await search_coro_func(keywords, group=self.group, cache=cache)
        except errors.RequestError as e:
            raise errors.SceneError(e)
        else:
            return self._handle_results(results)

    def _handle_results(self, results):
        results = natsort.natsorted(results, key=str.casefold)
        if not self.episodes:
            _log.debug('No episodes info: %r', self.episodes)
            return results
        else:
            _log.debug('Looking for episodes: %r', self.episodes)

            def match(result, wanted_seasons=tuple(self.episodes.items())):
                existing_seasons = release.ReleaseInfo(result)['episodes']
                for wanted_season, wanted_episodes in wanted_seasons:
                    for existing_season, existing_episodes in existing_seasons.items():
                        if wanted_episodes:
                            # Episode matches if any wanted episode is in the release
                            episode_match = any(e in existing_episodes for e in wanted_episodes)
                        else:
                            # Season pack wanted, so all episodes match
                            episode_match = True
                        # Season matches if seasons are equal or season is not specified
                        season_match = (wanted_season == existing_season or not wanted_season)
                        # Return if this result is a match (no other matches needed)
                        if season_match and episode_match:
                            return True

            return [r for r in results if match(r)]

    @property
    def keywords(self):
        """Sequence of search terms"""
        return self._keywords

    @property
    def group(self):
        """Release group name"""
        return self._group

    @property
    def episodes(self):
        """:class:`~.release.Episodes`-like mapping"""
        return self._episodes

    def __repr__(self):
        args = []
        if self.keywords:
            args.append(', '.join((repr(kw) for kw in self.keywords)))
        if self.group:
            args.append(f'group={self.group!r}')
        if self.episodes:
            args.append(f'episodes={self.episodes!r}')
        args_str = ', '.join(args)
        return f'{type(self).__name__}({args_str})'


_abbreviated_scene_filename_regexs = (
    # Match names with group in front
    re.compile(r'^[a-z0-9]+-[a-z0-9_\.-]+?(?!-[a-z]{2,})\.(?:mkv|avi)$'),
    # Match "ttl.720p-group.mkv"
    re.compile(r'^[a-z0-9]+[\.-]\d{3,4}p-[a-z]{2,}\.(?:mkv|avi)$'),
)

def assert_not_abbreviated_filename(filepath):
    """
    Raise :class:`~.errors.SceneError` if `filepath` points to an abbreviated
    scene release file name like ``abd-mother.mkv``
    """
    filename = os.path.basename(filepath)
    for regex in _abbreviated_scene_filename_regexs:
        if regex.search(filename):
            raise errors.SceneError(
                f'Provide parent directory of abbreviated scene file: {filename}'
            )
