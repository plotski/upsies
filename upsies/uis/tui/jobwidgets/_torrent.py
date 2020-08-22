from prompt_toolkit.application import get_app

from ....utils import cache
from .. import widgets
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class TorrentJobWidget(_base.JobWidgetBase):
    def setup(self):
        self._progress = widgets.ProgressBar()
        self.job.on_progress_update(self.handle_progress_update)
        self.job.on_finished(lambda _: get_app().invalidate())

    def activate(self):
        pass

    def handle_progress_update(self, percent_done):
        self._progress.percent = percent_done
        get_app().invalidate()

    @cache.property
    def runtime_widget(self):
        return self._progress
