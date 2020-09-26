from prompt_toolkit.application import get_app

from ....utils import cache
from .. import widgets
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ReleaseNameJobWidget(_base.JobWidgetBase):
    def setup(self):
        self._release_name = widgets.InputField(
            text='Loading...',
            on_accepted=self.handle_release_name,
            read_only=True,
        )

        # The global Release instance can run a callback whenever the release
        # name changes. This happens when a database entry (e.g. from IMDb) is
        # selected.
        def release_name_changed_callback(release_name):
            self._release_name.read_only = False
            self._release_name.text = release_name.format()
            get_app().invalidate()
        self.job.on_release_name_update(release_name_changed_callback)

    def activate(self):
        get_app().invalidate()

    def handle_release_name(self, buffer):
        _log.debug('Approved release name: %r', self._release_name.text)
        self.job.release_name_selected(self._release_name.text)

    @cache.property
    def runtime_widget(self):
        return self._release_name
