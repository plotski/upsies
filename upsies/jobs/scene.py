"""
Scene release search and check
"""

import asyncio

from .. import errors
from ..utils import cached_property, fs, scene, types
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

    @cached_property
    def cache_id(self):
        """
        Scene database name and final segment of the `content_path` argument to
        :meth:`initialize`
        """
        return (fs.basename(self._content_path),)

    def initialize(self, *, content_path):
        """
        Set internal state

        :param content_path: Path to video file or directory that contains a
            video file or release name
        """
        self._content_path = content_path
        self.signal.add('search_results')

    def execute(self):
        """Send search query"""
        try:
            query = scene.SceneQuery.from_string(self._content_path)
        except errors.SceneError as e:
            self.error(e, finish=True)
        else:
            self._search_task = asyncio.ensure_future(
                scene.search(query=query),
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


class SceneCheckJob(JobBase):
    """
    Verify scene release name and content

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``ask_release_name``
            Emitted if the user must pick a release name from multiple search
            results. Registered callbacks get a sequence of release names as
            positional argument.

        ``ask_is_scene_release``
            Emitted after we made our best guess and the user must approve or
            override it. Registered callbacks get a
            :class:`~.types.SceneCheckResult` enum as a positional argument.

        ``checked``
            Emitted after the user decided whether it's a scene release or not.
            Registered callbacks get a :class:`~.utils.types.SceneCheckResult`
            enum as a positional argument.
    """

    name = 'scene-check'
    label = 'Scene Check'
    hidden = False

    @cached_property
    def cache_id(self):
        """Final segment of the `content_path` argument to :meth:`initialize`"""
        return (fs.basename(self._content_path),)

    @property
    def is_scene_release(self):
        """
        :class:`~.utils.types.SceneCheckResult` enum or `None` before job is
        finished
        """
        return self._is_scene_release

    def initialize(self, *, content_path):
        """
        Set internal state

        :param content_path: Path to video file or directory that contains a
            video file or release name
        """
        self._content_path = content_path
        self._is_scene_release = None
        self._release_name = fs.strip_extension(fs.basename(content_path))
        self.signal.add('ask_release_name')
        self.signal.add('ask_is_scene_release')
        self.signal.add('checked')

    async def _catch_errors(self, coro):
        try:
            return await coro
        except errors.RequestError as e:
            self.error(e, finish=True)
        except errors.SceneError as e:
            self.error(e, finish=True)
        except BaseException as e:
            self.exception(e)

    def execute(self):
        """Start asynchronous background worker task"""
        asyncio.ensure_future(
            self._catch_errors(
                self._find_release_name()
            )
        )

    async def _find_release_name(self):
        is_scene_release = await scene.is_scene_release(self._content_path)
        if is_scene_release is types.SceneCheckResult.false:
            _log.debug('Not a scene release: %r', self._content_path)
            self._handle_scene_check_result(types.SceneCheckResult.false, exceptions=())
        else:
            # Find specific release name. If there are multiple search results,
            # ask the user to pick one.
            query = scene.SceneQuery.from_string(self._content_path)
            results = await scene.search(query, only_existing_releases=False)
            if not results:
                _log.debug('No search results: %r', self._content_path)
                self._handle_scene_check_result(types.SceneCheckResult.unknown, exceptions=())
            elif len(results) == 1:
                _log.debug('Auto-picking only search result: %r', results[0])
                release_name = results[0]
                await self._verify_release(release_name)
            elif self._release_name in results:
                _log.debug('Auto-picking from search results: %r', self._release_name)
                await self._verify_release(self._release_name)
            else:
                _log.debug('Asking for release name: %r', results)
                self.signal.emit('ask_release_name', results)

    def user_selected_release_name(self, release_name):
        """
        Must be called by the UI when the user picked a release name from search
        results

        :param release_name: Scene release name as :class:`str` or any falsy
            value for a non-scene release
        """
        _log.debug('User selected release name: %r', release_name)
        if release_name:
            asyncio.ensure_future(
                self._catch_errors(
                    self._verify_release(release_name)
                )
            )
        else:
            self._handle_scene_check_result(types.SceneCheckResult.false, exceptions=())

    async def _verify_release(self, release_name):
        _log.debug('Verifying release: %r', release_name)
        is_scene_release, exceptions = await scene.verify_release(self._content_path, release_name)
        self._handle_scene_check_result(is_scene_release, exceptions)

    def _handle_scene_check_result(self, is_scene_release, exceptions=()):
        _log.debug('Handling result: %r: %r', is_scene_release, exceptions)

        # Split exceptions into errors and warnings
        serious_errors = [e for e in exceptions if not isinstance(e, errors.SceneMissingInfoError)]
        warnings = [e for e in exceptions if isinstance(e, errors.SceneMissingInfoError)]
        for e in serious_errors:
            self.error(e)
        for e in warnings:
            self.warn(e)

        if serious_errors:
            self.finish()
        elif is_scene_release in (types.SceneCheckResult.true, types.SceneCheckResult.false):
            self.finalize(is_scene_release)
        else:
            self.signal.emit('ask_is_scene_release', is_scene_release)

    def finalize(self, is_scene_release):
        """
        Make the final decision of whether this is a scene release or not and
        :meth:`finish`

        Must be called by the UI in the handler of the signal
        ``ask_is_scene_release``.

        :param is_scene_release: :class:`~.types.SceneCheckResult` enum
        """
        _log.debug('User decided: %r', is_scene_release)
        self._is_scene_release = is_scene_release
        self.signal.emit('checked', is_scene_release)
        if is_scene_release is types.SceneCheckResult.true:
            self.send('Scene release')
        elif is_scene_release is types.SceneCheckResult.false:
            self.send('Not a scene release')
        else:
            self.send('May be a scene release')
        self.finish()
