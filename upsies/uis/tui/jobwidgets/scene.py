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
        self._release_name_dialog = widgets.RadioList(
            on_accepted=self._handle_dialog_release_name,
        )
        self._confirm_guess_dialog = widgets.RadioList(
            on_accepted=self._handle_dialog_confirm_guess,
        )
        self._current_dialog = None
        self.job.signal.register('ask_release_name', self._ask_release_name)
        self.job.signal.register('ask_is_scene_release', self._ask_is_scene_release)

    def _ask_release_name(self, release_names):
        _log.debug('Asking for release name: %r', release_names)
        choices = list(release_names)
        self._release_name_dialog.choices = choices
        self._current_dialog = self._release_name_dialog
        self.invalidate()

    def _handle_dialog_release_name(self, choice):
        _log.debug('Got release name: %r', choice)
        self._current_dialog = None
        self.invalidate()
        self.job.user_selected_release_name(choice)

    def _ask_is_scene_release(self, is_scene_release):
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

        self._confirm_guess_dialog.choices = (make_choice(True), make_choice(False))
        self._confirm_guess_dialog.focused_choice = make_choice(is_scene_release)
        self._current_dialog = self._confirm_guess_dialog
        self.invalidate()

    def _handle_dialog_confirm_guess(self, is_scene_release):
        _log.debug('Got confirmed guess: %r', is_scene_release)
        self._current_dialog = None
        self.invalidate()
        self.job.user_decided(is_scene_release[1])

    @cached_property
    def runtime_widget(self):
        return HSplit(
            children=[
                ConditionalContainer(
                    filter=Condition(lambda: self._current_dialog is self._release_name_dialog),
                    content=HSplit(
                        children=[
                            Window(FormattedTextControl('Pick the correct release name:')),
                            self._release_name_dialog,
                        ],
                    ),
                ),
                ConditionalContainer(
                    filter=Condition(lambda: self._current_dialog is self._confirm_guess_dialog),
                    content=HSplit(
                        children=[
                            Window(FormattedTextControl('Is this a scene release?')),
                            self._confirm_guess_dialog,
                        ],
                    ),
                ),
            ],
        )
