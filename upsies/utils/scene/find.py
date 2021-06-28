"""
Search for scene release
"""

import re

from ... import errors
from .. import LazyModule, release
from . import common, predb

import logging  # isort:skip
_log = logging.getLogger(__name__)

natsort = LazyModule(module='natsort', namespace=globals())


async def search(*args, **kwargs):
    """Search with the recommended :class:`~.SceneDbApiBase` subclass"""
    return await predb.PreDbApi().search(*args, **kwargs)


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

        # Replace H.264/5 with H264/5
        info['video_codec'] = re.sub(r'\.', '', info['video_codec'])

        # Replace WEB-DL with WEB
        if info.get('source') == 'WEB-DL':
            info['source'] = 'WEB'

        # Group and episodes are handled separately
        needed_keys = [k for k in common.get_needed_keys(info)
                       if k not in ('group', 'episodes')]
        keywords = [info[key] for key in needed_keys
                    if key in info]
        query = cls(
            *keywords,
            group=release.get('group', ''),
            episodes=info.get('episodes', {}),
        )
        _log.debug('SceneQuery from %r: %r', info, query)
        return query

    async def search(self, search_coro_func, only_existing_releases=True):
        """
        Pre-process query and post-process results from `search_coro_func`

        This is a wrapper function that tries to handle season/episode
        information more intuitively.

        :param search_coro_func: Coroutine function with the call signature
            `(keywords, group)` that returns a sequence of release names
        :param bool only_existing_releases: If this is truthy, the results
            contain all episodes for every season pack in :attr:`keywords`.
            Otherwise, fake season pack release names are included in the
            returned results.

        Any `keywords` that look like "S01", "S02E03", etc are removed in the
        search request. The search results are then filtered for the specific
        :attr:`episodes` given and returned in natural sort order.
        """
        keywords = tuple(kw for kw in self.keywords
                         if not re.match(r'^(?i:[SE]\d+|)+$', kw))
        _log.debug('Searching for scene release: %r', keywords)
        results = await search_coro_func(keywords, group=self.group)
        return self._handle_results(results, only_existing_releases)

    def _handle_results(self, results, only_existing_releases=True):
        def sorted_and_deduped(results):
            return natsort.natsorted(set(results), key=str.casefold)

        if not self.episodes:
            _log.debug('No episodes info: %r', self.episodes)
            return sorted_and_deduped(results)
        else:
            _log.debug('Looking for existing episodes: %r', self.episodes)

            def get_wanted_episodes(season):
                # Combine episodes from any season ('') with episodes from given season
                eps = None
                if '' in self.episodes:
                    eps = self.episodes['']
                if season in self.episodes:
                    eps = (eps or ()) + self.episodes[season]
                return eps

            # Translate single episodes into season packs.
            matches = []
            for result in results:
                for result_season, result_eps in release.Episodes.from_string(result).items():
                    wanted_episodes = get_wanted_episodes(result_season)
                    # () means season pack
                    if wanted_episodes == ():
                        if only_existing_releases:
                            # Add episode from wanted season pack
                            _log.debug('Adding episode from season pack: %r', result)
                            matches.append(result)
                        else:
                            season_pack = self._create_season_pack_name(result)
                            _log.debug('Adding season pack: %r', season_pack)
                            matches.append(season_pack)
                    elif wanted_episodes is not None:
                        for ep in result_eps:
                            if ep in wanted_episodes:
                                matches.append(result)
                                break

            return sorted_and_deduped(matches)

    @staticmethod
    def _create_season_pack_name(release_name):
        # Remove episode from release name to create season pack name
        season_pack = re.sub(r'\b(S\d{2,})E\d{2,}\b', r'\1', release_name)

        # Remove episode title
        release_info = release.ReleaseInfo(release_name)
        if release_info['episode_title']:
            # Escape special characters in each word and
            # join words with "space or period" regex
            episode_title_regex = r'[ \.]{1,}'.join(
                re.escape(word)
                for word in release_info['episode_title'].split()
            )
            season_pack = re.sub(rf'\b{episode_title_regex}\W', '', season_pack)

        return season_pack

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
