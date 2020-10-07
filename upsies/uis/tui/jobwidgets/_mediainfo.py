from ....utils import cache
from .. import widgets
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
        return widgets.TextField('')
