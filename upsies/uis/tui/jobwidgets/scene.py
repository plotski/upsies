from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import (ConditionalContainer, HSplit,
                                              Window)
from prompt_toolkit.layout.controls import FormattedTextControl

from ....utils import cached_property
from ....utils.types import SceneCheckResult
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SceneSearchJobWidget(JobWidgetBase):
    def setup(self):
        pass

    @cached_property
    def runtime_widget(self):
        return None


class SceneCheckJobWidget(JobWidgetBase):
    def setup(self):
        self._release_name_prompt = widgets.RadioList(
            on_accepted=self._handle_prompt_release_name,
        )
        self._confirm_guess_prompt = widgets.RadioList(
            on_accepted=self._handle_prompt_confirm_guess,
        )
        self._current_prompt = None
        self.job.signal.register('prompt_release_name', self._prompt_release_name)
        self.job.signal.register('prompt_is_scene_release', self._prompt_is_scene_release)

    def _prompt_release_name(self, release_names):
        _log.debug('Prompting for release name: %r', release_names)
        choices = list(release_names)
        self._release_name_prompt.choices = choices
        self._current_prompt = self._release_name_prompt
        self.invalidate()

    def _handle_prompt_release_name(self, choice):
        _log.debug('Got release name: %r', choice)
        self._current_prompt = None
        self.invalidate()
        self.job.user_selected_release_name(choice)

    def _prompt_is_scene_release(self, is_scene_release):
        _log.debug('Confirming guess: %r', is_scene_release)

        def make_choice(choice):
            if choice:
                string = 'Yes'
                if is_scene_release is SceneCheckResult.true:
                    string += ' (auto-detected)'
                return (string, SceneCheckResult.true)
            else:
                string = 'No'
                if is_scene_release is SceneCheckResult.false:
                    string += ' (auto-detected)'
                return (string, SceneCheckResult.false)

        self._confirm_guess_prompt.choices = (make_choice(True), make_choice(False))
        self._confirm_guess_prompt.focused_choice = make_choice(is_scene_release)
        self._current_prompt = self._confirm_guess_prompt
        self.invalidate()

    def _handle_prompt_confirm_guess(self, is_scene_release):
        _log.debug('Got confirmed guess: %r', is_scene_release)
        self._current_prompt = None
        self.invalidate()
        self.job.user_decided(is_scene_release[1])

    @cached_property
    def runtime_widget(self):
        return HSplit(
            children=[
                ConditionalContainer(
                    filter=Condition(lambda: self._current_prompt is self._release_name_prompt),
                    content=HSplit(
                        children=[
                            Window(FormattedTextControl('Pick the correct release name:')),
                            self._release_name_prompt,
                        ],
                    ),
                ),
                ConditionalContainer(
                    filter=Condition(lambda: self._current_prompt is self._confirm_guess_prompt),
                    content=HSplit(
                        children=[
                            Window(FormattedTextControl('Is this a scene release?')),
                            self._confirm_guess_prompt,
                        ],
                    ),
                ),
            ],
        )
