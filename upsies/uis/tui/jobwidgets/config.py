from ....utils import cached_property
from . import JobWidgetBase

# This job is hidden so we only need a dummy widget.

class SetJobWidget(JobWidgetBase):
    def setup(self):
        pass

    @cached_property
    def runtime_widget(self):
        return None
