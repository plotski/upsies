from ....utils import cache
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ChoiceJobWidget(JobWidgetBase):
    def setup(self):
        self._radiolist = widgets.RadioList(
            choices=self.job.choices,
            focused=self.job.focused,
            on_accepted=self.handle_choice,
        )

    def handle_choice(self, choice):
        self.job.choice_selected(choice)

    @cache.property
    def runtime_widget(self):
        return self._radiolist
