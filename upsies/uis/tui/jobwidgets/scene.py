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

    # Force this job to be interactive. Autodetection doesn't work because
    # potential dialogs pop up when we get a reply to a scenedb query.
    is_interactive = True

    def setup(self):
        self._question = FormattedTextControl('')
        self._radiolist = widgets.RadioList()
        self._dialog_enabled = False
        self.job.signal.register('ask_release_name', self._ask_release_name)
        self.job.signal.register('ask_is_scene_release', self._ask_is_scene_release)

    def _ask_release_name(self, release_names):
        _log.debug('Asking for release name: %r', release_names)

        def handle_release_name(choice):
            _log.debug('Got release name: %r', choice)
            self._dialog_enabled = False
            self.invalidate()
            self.job.user_selected_release_name(choice[1])

        self._radiolist.on_accepted = handle_release_name
        self._radiolist.choices = [(release_name, release_name) for release_name in release_names]
        self._radiolist.choices.append(('This is not a scene release', None))

        self._question.text = 'Pick the correct release name:'
        self._dialog_enabled = True
        self.invalidate()

    def _ask_is_scene_release(self, is_scene_release):
        _log.debug('Confirming guess: %r', is_scene_release)

        def make_choice(choice):
            if choice:
                string = 'Yes'
                if is_scene_release is SceneCheckResult.true:
                    string += ' (autodetected)'
                return (string, SceneCheckResult.true)
            else:
                string = 'No'
                if is_scene_release is SceneCheckResult.false:
                    string += ' (autodetected)'
                return (string, SceneCheckResult.false)

        def handle_is_scene_release(choice):
            _log.debug('Got decision from user: %r', choice)
            self._dialog_enabled = False
            self.invalidate()
            self.job.finalize(choice[1])

        self._radiolist.choices = (make_choice(True), make_choice(False))
        self._radiolist.focused_choice = make_choice(is_scene_release)
        self._radiolist.on_accepted = handle_is_scene_release

        self._question.text = 'Is this a scene release?'
        self._dialog_enabled = True
        self.invalidate()

    @cached_property
    def runtime_widget(self):
        return HSplit(
            children=[
                ConditionalContainer(
                    filter=Condition(lambda: self._dialog_enabled),
                    content=HSplit(
                        children=[
                            Window(self._question),
                            self._radiolist,
                        ],
                    ),
                ),
            ],
        )
