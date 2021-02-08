"""
Scene release search and check
"""

import asyncio

from .. import errors
from ..utils import cached_property, fs, release, scene
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
        self.signal.add('search_results')

    def execute(self):
        """Send search query"""
        try:
            query = scene.SceneQuery.from_string(self._content_path)
        except errors.SceneError as e:
            self.error(e)
            self.finish()
        else:
            self._search_task = asyncio.ensure_future(
                self._scenedb.search(query=query, cache=not self.ignore_cache)
            )
            self._search_task.add_done_callback(self._handle_results)

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
