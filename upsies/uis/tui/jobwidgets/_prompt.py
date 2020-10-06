from prompt_toolkit.application import get_app

from ....utils import cache
from .. import widgets
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ChoiceJobWidget(_base.JobWidgetBase):
    def setup(self):
        self._radiolist = widgets.RadioList(
            choices=self.job.choices,
            focused=self.job.focused,
            on_accepted=self.handle_choice,
        )

    def activate(self):
        get_app().invalidate()

    def handle_choice(self, choice):
        self.job.choice_selected(choice)

    @cache.property
    def runtime_widget(self):
        return self._radiolist
