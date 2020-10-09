from prompt_toolkit.layout.containers import Window

from ....utils import cache
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class MediainfoJobWidget(JobWidgetBase):
    def setup(self):
        pass

    def activate(self):
        pass

    @cache.property
    def runtime_widget(self):
        return Window(dont_extend_height=True)
