"""
Scene release search and check
"""

from .. import errors
from ..utils import fs, scene, types
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

    @property
    def cache_id(self):
        """Final segment of `content_path`"""
        return fs.basename(self._content_path)

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
        self.add_task(self._search(), finish_when_done=True)

    async def _search(self):
        try:
            query = scene.SceneQuery.from_string(self._content_path)
        except errors.SceneError as e:
            self.error(e)
        else:
            try:
                results = await scene.search(query)
            except (errors.RequestError, errors.SceneError) as e:
                self.error(e)
            else:
                _log.debug('Handling results: %r', results)
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

    @property
    def cache_id(self):
        """Final segment of `content_path`"""
        return fs.basename(self._content_path)

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
        self.signal.record('checked')
        self.signal.register('checked', lambda is_scene: setattr(self, '_is_scene_release', is_scene))

    async def _catch_errors(self, coro):
        try:
            return await coro
        except errors.RequestError as e:
            self.warn(e)
            self.signal.emit('ask_is_scene_release', types.SceneCheckResult.unknown)
        except errors.SceneError as e:
            self.error(e)

    def execute(self):
        """Start asynchronous background worker task"""
        self.add_task(
            self._catch_errors(
                self._find_release_name()
            )
        )

    async def _find_release_name(self):
        is_scene_release = await scene.is_scene_release(self._content_path)
        if is_scene_release is types.SceneCheckResult.false:
            _log.debug('Not a scene release: %r', self._content_path)
            self._handle_scene_check_result(types.SceneCheckResult.false)
        else:
            # Find specific release name. If there are multiple search results,
            # ask the user to pick one.
            query = scene.SceneQuery.from_string(self._content_path)
            results = await scene.search(query, only_existing_releases=False)
            if not results:
                _log.debug('No search results: %r', self._content_path)
                self._handle_scene_check_result(types.SceneCheckResult.unknown)

            # Autopick if release name is in search results
            elif self._release_name in results:
                _log.debug('Autopicking from search results: %r', self._release_name)
                await self._verify_release(self._release_name)

            # Autopick single result if we know it's a scene release. If there
            # is missing information (e.g. no group), is_scene_release() returns
            # SceneCheckResult.unknown and we ask the user.
            elif len(results) == 1 and is_scene_release is types.SceneCheckResult.true:
                release_name = results[0]
                _log.debug('Autopicking only search result: %r', release_name)
                await self._verify_release(release_name)

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
            self.add_task(
                self._catch_errors(
                    self._verify_release(release_name)
                )
            )
        else:
            self._handle_scene_check_result(types.SceneCheckResult.false)

    async def _verify_release(self, release_name):
        _log.debug('Verifying release: %r', release_name)
        is_scene_release, exceptions = await scene.verify_release(self._content_path, release_name)
        self._handle_scene_check_result(is_scene_release, exceptions)

    def _handle_scene_check_result(self, is_scene_release, exceptions=()):
        _log.debug('Handling result: %r: %r', is_scene_release, exceptions)

        warnings = [e for e in exceptions if isinstance(e, errors.SceneMissingInfoError)]
        for e in warnings:
            self.warn(e)

        serious_errors = [e for e in exceptions if not isinstance(e, errors.SceneMissingInfoError)]
        for e in serious_errors:
            self.error(e)

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
        self.signal.emit('checked', is_scene_release)
        if is_scene_release is types.SceneCheckResult.true:
            self.send('Scene release')
        elif is_scene_release is types.SceneCheckResult.false:
            self.send('Not a scene release')
        else:
            self.send('May be a scene release')
        self.finish()
