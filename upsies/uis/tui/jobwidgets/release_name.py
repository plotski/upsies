from ....utils import cached_property
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ReleaseNameJobWidget(JobWidgetBase):
    def setup(self):
        self._input = widgets.InputField(
            style='class:dialog.text',
            on_accepted=self._handle_approved_release_name,
            read_only=True,
        )
        self.job.signal.register('release_name_updating', self._start_throbber)
        self.job.signal.register('release_name_updated', self._set_input)

    def _start_throbber(self):
        self._input.is_loading = True

    def _set_input(self, release_name):
        self._input.is_loading = False
        self._input.read_only = False
        self._input.text = self._get_release_name_string(release_name)
        self.invalidate()

    def _get_release_name_string(self, release_name):
        # TODO: Use custom format specified by some attribute on self.job.
        return release_name.format()

    def _handle_approved_release_name(self, _):
        self.job.release_name_selected(self._input.text)

    @cached_property
    def runtime_widget(self):
        return self._input
