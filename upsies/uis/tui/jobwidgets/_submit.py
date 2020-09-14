import functools

from prompt_toolkit.application import get_app

from ....utils import cache
from .. import widgets
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmissionJobWidget(_base.JobWidgetBase):
    def setup(self):
        self._status_info = widgets.TextField(
            text='Waiting...',
        )
        callbacks = (
            (self.job.signal.logging_in, 'Logging in...'),
            (self.job.signal.logged_in, 'Logged in successfully.'),
            (self.job.signal.submitting, 'Submitting torrent...'),
            (self.job.signal.submitted, 'Submitted torrent successfully.'),
            (self.job.signal.logging_out, 'Logging out...'),
            (self.job.signal.logged_out, 'Logged out successfully.'),
        )
        for signal, msg in callbacks:
            self.job.on(signal, functools.partial(self._set_status, msg))

    def activate(self):
        pass

    @cache.property
    def runtime_widget(self):
        return self._status_info

    def _set_status(self, message):
        self._status_info.text = message
        get_app().invalidate()
