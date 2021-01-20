from ....utils import cached_property
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ReleaseNameJobWidget(JobWidgetBase):
    def setup(self):
        self._release_name = widgets.InputField(
            text='Loading...',
            style='class:prompt.text',
            on_accepted=self.handle_release_name,
            read_only=True,
        )

        def release_name_changed_callback(release_name):
            self._release_name.read_only = False
            self._release_name.text = release_name.format()
            self.invalidate()

        self.job.signal.register('release_name_updated', release_name_changed_callback)

    def handle_release_name(self, buffer):
        _log.debug('Approved release name: %r', self._release_name.text)
        self.job.release_name_selected(self._release_name.text)

    @cached_property
    def runtime_widget(self):
        return self._release_name
