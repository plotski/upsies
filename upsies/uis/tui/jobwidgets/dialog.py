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
            on_accepted=self._handle_accepted,
        )
        self.job.signal.register('dialog_updated', self._handle_dialog_updated)

    def _handle_dialog_updated(self, job):
        self._radiolist.choices = job.choices
        self._radiolist.focused_index = job.focused_index
        self.invalidate()

    def _handle_accepted(self, choice):
        self.job.choice_selected(choice)

    @cached_property
    def runtime_widget(self):
        return self._radiolist
