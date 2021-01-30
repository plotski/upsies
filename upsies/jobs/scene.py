"""
Scene release search and check
"""

import asyncio

from .. import errors
from ..utils import cached_property, fs, release
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SceneSearchJob(JobBase):
    """
    Search for scene release

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``search_results``
            Emitted after new search results are available. Registered callbacks
            get a sequence of release names (:class:`str`) as a positional
            argument.
    """

    name = 'scene-search'
    label = 'Scene Search'
    hidden = True
    default_scenedb = 'predb'

    @cached_property
    def cache_id(self):
        """
        Scene database name and final segment of the `content_path` argument to
        :meth:`initialize`
        """
        return (self._scenedb.name, fs.basename(self._content_path))

    def initialize(self, *, scenedb, content_path):
        """
        Set internal state

        :param SceneDbApiBase scenedb: Return value of :func:`.scene.scenedb`
        :param content_path: Path to video file or directory that contains a
            video file or release name
        """
        self._scenedb = scenedb
        self._content_path = content_path
        self._release_info = release.ReleaseInfo(content_path)
        self.signal.add('search_results')

    def execute(self):
        """Send search query"""
        self._search_task = asyncio.ensure_future(self._search())
        self._search_task.add_done_callback(self._handle_results)

    async def _search(self):
        info = dict(self._release_info)

        # Format season and episode(s)
        if info['season']:
            info['season_episode'] = f'S{info["season"]:0>2}'
            if info['episode']:
                if isinstance(info['episode'], str):
                    # Single episode
                    info['season_episode'] += f'E{info["episode"]:0>2}'
                else:
                    # Multi-episode (e.g. "S01E01E02")
                    info['season_episode'] += ''.join((
                        f'E{episode:0>2}' for episode in info['episode']
                    ))

        # Build positional arguments
        args = [info['title']]
        for key in ('year', 'season_episode', 'resolution', 'source', 'video_codec'):
            if info.get(key):
                args.append(info[key])

        # Build keyword arguments
        kwargs = {'cache': not self.ignore_cache}
        if self._release_info['group']:
            kwargs['group'] = self._release_info['group']

        # Perform search
        results = await self._scenedb.search(*args, **kwargs)
        return results

    def _handle_results(self, task):
        try:
            results = task.result()
            _log.debug('Handling results: %r', results)
        except errors.SceneError as e:
            self.error(e)
        else:
            if results:
                for result in results:
                    self.send(result)
            else:
                self.error('No results')
            self.signal.emit('search_results', results)
        finally:
            self.finish()
