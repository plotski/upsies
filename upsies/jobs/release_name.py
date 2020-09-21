import asyncio

from ..tools import release_name
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ReleaseNameJob(_base.JobBase):
    name = 'release-name'
    label = 'Release Name'

    @property
    def release_name(self):
        """:class:`ReleaseName` instance"""
        return self._release_name

    def initialize(self, content_path):
        self._release_name = release_name.ReleaseName(content_path)
        self._release_name_update_callbacks = []

    def execute(self):
        pass

    def release_name_selected(self, name):
        """
        Must be called by the UI when the user accepts the release name

        :param str name: Release name as accepted by the user
        """
        if name:
            self.send(name, if_not_finished=True)
        self.finish()

    def fetch_info(self, *args, **kwargs):
        kwargs['callback'] = self.handle_release_name_update
        asyncio.ensure_future(
            self.release_name.fetch_info(*args, **kwargs),
        )

    def handle_release_name_update(self, release_name):
        for cb in self._release_name_update_callbacks:
            cb(release_name)

    def on_release_name_update(self, callback):
        self._release_name_update_callbacks.append(callback)
