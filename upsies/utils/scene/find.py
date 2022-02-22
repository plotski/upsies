"""
Search for scene release
"""

import collections
import re

from ... import constants, errors
from .. import LazyModule, asyncmemoize, fs, release
from . import common, verify

import logging  # isort:skip
_log = logging.getLogger(__name__)

natsort = LazyModule(module='natsort', namespace=globals())


@asyncmemoize
async def search(query, dbs=('predbovh', 'srrdb'), only_existing_releases=None):
    """
    Search scene databases

    Try to get search results from multiple :class:`~.base.SceneDbApiBase`
    instances and return the first response.

    Failed requests are ignored unless all requests fail, in which case they are
    combined into a single :class:`~.errors.RequestError`.

    If there are no results and `query` is a directory path that looks like a
    season pack, perform one search per video file in that directory or any
    subdirectory. This is necessary to find mixed season packs.

    :param query: :class:`SceneQuery` object or :class:`str` to pass to
        :meth:`SceneQuery.from_string` or :class:`~.collections.abc.Mapping` to
        pass to :meth:`SceneQuery.from_release`
    :param dbs: Sequence of :attr:`~.base.SceneDbApiBase.name` values
    :param only_existing_releases: See :meth:`.SceneQuery.search`

    :return: Sequence of release names (:class:`str`)

    :raise RequestError: if all search requests fail
    """
    path = None
    if isinstance(query, str):
        path = query
        query = SceneQuery.from_string(query)
    elif isinstance(query, collections.abc.Mapping):
        query = SceneQuery.from_release(query)

    results = await _multisearch(dbs, query, only_existing_releases)
    if results:
        return results
    elif path:
        combined_results = []
        for episode_query in _generate_episode_queries(path):
            results = await _multisearch(dbs, episode_query, only_existing_releases)
            combined_results.extend(results)
        return combined_results


async def _multisearch(dbs, query, only_existing_releases):
    # Send the same query to multiple DBs
    from . import scenedb

    exceptions = []
    for db_name in dbs:
        db = scenedb(db_name)
        try:
            results = await db.search(query, only_existing_releases=only_existing_releases)
        except errors.RequestError as e:
            _log.debug('Collecting scene search error: %r', e)
            exceptions.append(e)
        else:
            _log.debug('Returning scene search results: %r', results)
            return results

    if exceptions:
        msg = 'All queries failed: ' + ', '.join(str(e) for e in exceptions)
        raise errors.RequestError(msg)
    else:
        return []


def _generate_episode_queries(path):
    info = release.ReleaseInfo(path)
    if info['type'] is release.ReleaseType.season:
        # Create `query` from each `episode_path`
        episode_paths = fs.file_list(path, extensions=constants.VIDEO_FILE_EXTENSIONS)
        for episode_path in episode_paths:
            _log.debug('Creating query for episode: %r', episode_path)
            if not verify.is_abbreviated_filename(episode_path):
                yield SceneQuery.from_string(episode_path)


class SceneQuery:
    """
    Query for scene release databases

    :param keywords: Search keywords
    :param group: Release group name
    :param episodes: :class:`~.release.Episodes`-like mapping
    """

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
            return cls.from_release(release.ReleaseInfo(string, strict=False))
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
        # Replace H.264/5 with H264/5
        release['video_codec'] = re.sub(r'\.', '', release.get('video_codec', ''))

        # Replace WEB-DL with WEB
        if release.get('source') == 'WEB-DL':
            release['source'] = 'WEB'

        # Group and episodes are handled separately from the other keywords
        needed_keys = [k for k in common.get_needed_keys(release)
                       if k not in ('group', 'episodes')]
        keywords = [release[key] for key in needed_keys
                    if key in release]

        # Add single episode ("SxxEyy"), but not season pack ("Sxx") or anything
        # else (e.g. "SxxEyyEzz")
        seasons = tuple(release.get('episodes', {}).keys())
        episodes = tuple(episode
                         for episodes in release.get('episodes', {}).values()
                         for episode in episodes)
        if len(seasons) == 1 and len(episodes) == 1 and seasons[0] and episodes[0]:
            try:
                season = int(seasons[0])
                episode = int(episodes[0])
            except (ValueError, TypeError):
                pass
            else:
                keywords.append(f'S{season:02d}E{episode:02d}')

        query = cls(
            *keywords,
            group=release.get('group', ''),
            episodes=release.get('episodes', {}),
        )
        _log.debug('SceneQuery from %r: %r', release, query)
        return query

    def __init__(self, *keywords, group='', episodes={}):
        # Split each keyword at spaces
        kws = (k.strip()
               for kw in keywords
               for k in str(kw).split())

        # Remove season packs (keep "SxxEyy" but not "Sxx") because scene
        # releases are not season packs and we don't find anything if we look
        # for "S05". For season packs, we try to find all episodes of all
        # seasons and extract the relevant episodes in _handle_results().
        def exclude_season_pack(kw):
            if release.Episodes.is_episodes_info(kw):
                episodes = release.Episodes.from_string(kw)
                for season in tuple(episodes):
                    if not episodes[season]:
                        del episodes[season]
                return str(episodes)
            else:
                return kw

        kws = (exclude_season_pack(kw) for kw in kws)

        # Remove empty keywords
        # (I forgot why "-" is removed. Please explain if you know!)
        kws = (kw for kw in kws
               if kw and kw != '-')

        self._keywords = tuple(kws)
        self._group = str(group) if group else None
        self._episodes = episodes

    async def search(self, search_coro_func, only_existing_releases=None):
        """
        Pre-process query and post-process results from `search_coro_func`

        This is a wrapper function that tries to handle season/episode
        information more intuitively.

        :param search_coro_func: Coroutine function with the call signature
            `(keywords, group)` that returns a sequence of release names
        :param bool only_existing_releases: If this is truthy (the default), the
            results contain all episodes for every season pack in
            :attr:`keywords`. Otherwise, fake season pack release names are
            included in the returned results.
        """
        if only_existing_releases is None:
            only_existing_releases = True
        results = await search_coro_func(self.keywords, group=self.group)
        return self._handle_results(results, only_existing_releases)

    def _handle_results(self, results, only_existing_releases):
        def sorted_and_deduped(results):
            return natsort.natsorted(set(results), key=str.casefold)

        if not self.episodes:
            _log.debug('No episodes info: %r', self.episodes)
            return sorted_and_deduped(results)
        else:
            _log.debug('Looking for existing episodes: %r', self.episodes)

            def get_wanted_episodes(season):
                # Combine episodes from any season with episodes from given
                # season (season being empty string means "any season")
                eps = None
                if '' in self.episodes:
                    eps = self.episodes['']
                if season in self.episodes:
                    eps = (eps or []) + self.episodes[season]
                return eps

            # Translate single episodes into season packs.
            matches = []
            for result in results:
                for result_season, result_eps in release.Episodes.from_string(result).items():
                    wanted_episodes = get_wanted_episodes(result_season)

                    # [] means season pack
                    if wanted_episodes == []:
                        if only_existing_releases:
                            # Add episode from wanted season pack
                            _log.debug('Adding episode from season pack: %r', result)
                            matches.append(result)
                        else:
                            season_pack = common.get_season_pack_name(result)
                            _log.debug('Adding season pack: %r', season_pack)
                            matches.append(season_pack)

                    elif wanted_episodes is not None:
                        for ep in result_eps:
                            if ep in wanted_episodes:
                                matches.append(result)
                                break

            return sorted_and_deduped(matches)

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

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self.keywords == other.keywords
                and self.group == other.group
                and self.episodes == other.episodes
            )
        else:
            return NotImplemented
