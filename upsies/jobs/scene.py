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
        """Create background search task"""
        self.add_task(self._search(), finish_when_done=True)

    async def _search(self):
        try:
            results = await scene.search(self._content_path)
        except (errors.RequestError, errors.SceneError) as e:
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

    def initialize(self, *, content_path, force=None):
        """
        Set internal state

        :param content_path: Path to video file or directory that contains a
            video file or release name
        :param bool force: Predetermined check result; `True` (is scene),
            `False` (is not scene) or `None` (autodetect)
        """
        self._content_path = content_path
        self._predetermined_result = None if force is None else bool(force)
        self._is_scene_release = None
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
        if self._predetermined_result is None:
            self.add_task(
                self._catch_errors(
                    self._verify(),
                ),
            )
        elif self._predetermined_result is True:
            self.finalize(types.SceneCheckResult.true)
        elif self._predetermined_result is False:
            self.finalize(types.SceneCheckResult.false)
        else:
            raise RuntimeError(f'Unexpected predetermined_result: {self._predetermined_result!r}')

    async def _verify(self):
        _log.debug('Verifying release: %r', self._content_path)
        if await scene.is_scene_release(self._content_path) is types.SceneCheckResult.false:
            # Try to get a true negative as fast as possible
            self.finalize(types.SceneCheckResult.false)

        elif await scene.is_mixed_scene_release(self._content_path):
            # We don't want to prompt the user if this is a mixed release
            await self._verify_release()

        else:
            results = await scene.search(self._content_path, only_existing_releases=False)
            if len(results) >= 2:
                # If there are multiple search results, ask the user which one
                # `content_path` is supposed to be
                self.signal.emit('ask_release_name', results)
            else:
                await self._verify_release()

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

    async def _verify_release(self, release_name=None):
        is_scene_release, exceptions = await scene.verify_release(self._content_path, release_name)
        self._handle_scene_check_result(is_scene_release, exceptions)

    def _handle_scene_check_result(self, is_scene_release, exceptions=()):
        _log.debug('Handling result: %r: %r', is_scene_release, exceptions)

        warnings = [e for e in exceptions if isinstance(e, errors.SceneMissingInfoError)]
        for e in warnings:
            self.warn(e)

        serious_errors = [e for e in exceptions if not isinstance(e, errors.SceneMissingInfoError)]
        for e in serious_errors:
            self.error(e, finish=False)

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
        _log.debug('Final scene check decision: %r', is_scene_release)
        self.signal.emit('checked', is_scene_release)
        if is_scene_release is types.SceneCheckResult.true:
            self.send('Scene release')
        elif is_scene_release is types.SceneCheckResult.false:
            self.send('Not a scene release')
        else:
            self.send('May be a scene release')
        self.finish()
