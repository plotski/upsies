from ....utils import cached_property
from . import JobWidgetBase


class SubmitJobWidget(JobWidgetBase):
    def setup(self):
        pass

    @cached_property
    def runtime_widget(self):
        return None
