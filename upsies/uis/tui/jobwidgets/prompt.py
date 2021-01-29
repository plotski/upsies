from ....utils import cached_property
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ChoiceJobWidget(JobWidgetBase):
    def setup(self):
        self._radiolist = widgets.RadioList(
            choices=self.job.choices,
            focused=self.job.focused,
            on_accepted=self._handle_choice,
        )
        self.job.signal.register('prompt_updated', self._handle_update)

    def _handle_update(self):
        self._radiolist.choices = self.job.choices
        self._radiolist.focused_index = self.job.choices.index(self.job.focused)
        self.invalidate()

    def _handle_choice(self, choice):
        self.job.choice_selected(choice)

    @cached_property
    def runtime_widget(self):
        return self._radiolist
