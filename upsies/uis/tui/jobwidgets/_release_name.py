from prompt_toolkit.application import get_app

from ....utils import cache
from .. import widgets
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ReleaseNameJobWidget(_base.JobWidgetBase):
    def setup(self):
        self._release_name = widgets.InputField(
            text=str(self.job.release_name),
            on_accepted=self.handle_release_name,
        )

        # The global Release instance can run a callback whenever the release
        # name changes. This happens when a database entry (e.g. from IMDb) is
        # selected.
        def release_name_changed_callback(release_name):
            rn = release_name.format()
            _log.debug('Release name changed: %r', rn)
            if rn:
                self._release_name.text = rn
                get_app().invalidate()
        self.job.on_release_name_updated(release_name_changed_callback)

    def activate(self):
        pass

    def handle_release_name(self, buffer):
        _log.debug('Approved release name: %r', self._release_name.text)
        self.job.release_name_selected(self._release_name.text)

    @cache.property
    def runtime_widget(self):
        return self._release_name
