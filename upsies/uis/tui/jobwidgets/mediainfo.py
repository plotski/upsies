from ....utils import cached_property
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class MediainfoJobWidget(JobWidgetBase):
    def setup(self):
        pass

    @cached_property
    def runtime_widget(self):
        return None
