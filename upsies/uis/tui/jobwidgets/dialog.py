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
        # This also finishes self.job
        self.job.choice = choice

    @cached_property
    def runtime_widget(self):
        return self._radiolist


class TextFieldJobWidget(JobWidgetBase):
    def setup(self):
        self._input_field = widgets.InputField(
            text=self.job.text,
            read_only=self.job.read_only,
            style='class:dialog.text',
            on_accepted=self._handle_accepted,
        )
        self.job.signal.register('dialog_updating', self._handle_dialog_updating)
        self.job.signal.register('dialog_updated', self._handle_dialog_updated)

    def _handle_dialog_updating(self, job):
        self._input_field.is_loading = True

    def _handle_dialog_updated(self, job):
        self._input_field.is_loading = False
        self._input_field.read_only = job.read_only
        self._input_field.text = job.text
        self.invalidate()

    def _handle_accepted(self, buffer):
        self.job.send(buffer.text)

    @cached_property
    def runtime_widget(self):
        return self._input_field
