import asyncio

from ..tools import release_name
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ReleaseName(_base.JobBase):
    name = 'release-name'
    label = 'Release Name'

    @property
    def release_name(self):
        return self._release_name

    def initialize(self, content_path):
        self._release_name = release_name.ReleaseName(content_path)
        self._release_name_update_callbacks = []

    def execute(self):
        pass

    def fetch_info(self, id, db):
        async def fetch_info(id, db, self=self):
            info = await db.info(
                id,
                db.title_english,
                db.title_original,
                db.year,
            )
            self.release_name.title = info['title_original']
            self.release_name.title_aka = info['title_english']
            self.release_name.title_english = info['title_english']
            self.release_name.year = info['year']
            _log.debug('Release name updated: %s', self.name)
            for cb in self._release_name_update_callbacks:
                cb(self.release_name)

        asyncio.ensure_future(fetch_info(id, db))

    def on_release_name_updated(self, callback):
        self._release_name_update_callbacks.append(callback)

    def release_name_selected(self, name):
        if name:
            self.send(name, if_not_finished=True)
        self.finish()
