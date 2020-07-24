from ....utils import cache
from .. import widgets
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmissionJobWidget(_base.JobWidgetBase):
    def setup(self):
        self._status_info = widgets.TextField(
            text='<Status information>',
        )

    def activate(self):
        pass

    @cache.property
    def runtime_widget(self):
        return self._status_info
