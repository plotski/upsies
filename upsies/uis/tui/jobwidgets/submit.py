from ....utils import cached_property
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmitJobWidget(JobWidgetBase):
    def setup(self):
        signals = (
            'logging_in',
            'logged_in',
            'uploading',
            'uploaded',
            'logging_out',
            'logged_out',
        )
        for signal in signals:
            self.job.signal.register(signal, self.invalidate)

    @cached_property
    def runtime_widget(self):
        return None
