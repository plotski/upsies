from ....utils import cache
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SetJobWidget(JobWidgetBase):
    def setup(self):
        if self.job.output:
            self._setting = widgets.TextField(self.job.output[0])
        else:
            self._setting = widgets.TextField()

    @cache.property
    def runtime_widget(self):
        return self._setting
