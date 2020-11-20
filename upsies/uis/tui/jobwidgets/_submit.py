import functools

from ....utils import cache
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmitJobWidget(JobWidgetBase):
    def setup(self):
        self._status_info = widgets.TextField(
            text='Waiting...',
        )
        messages = (
            ('logging_in', 'Logging in...'),
            ('logged_in', 'Logged in successfully.'),
            ('uploading', 'Uploading...'),
            ('uploaded', 'Uploaded successfully.'),
            ('logging_out', 'Logging out...'),
            ('logged_out', 'Logged out successfully.'),
        )
        for signal, msg in messages:
            self.job.signal.register(signal, functools.partial(self._set_status, msg))

    @cache.property
    def runtime_widget(self):
        return self._status_info

    def _set_status(self, message):
        self._status_info.text = message
        self.invalidate()
