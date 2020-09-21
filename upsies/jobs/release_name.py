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

    def fetch_info(self, id, db):
        """
        Fill in some information from IMDb or similar service

        :param str id: ID to query DB for
        :param str db: One of the modules in :mod:`tools`
        """
        async def fetch_info(id, db, self=self):
            info = await db.info(
                id,
                db.title_english,
                db.title_original,
                db.year,
            )
            rn = self.release_name
            rn.title = info['title_original']
            rn.title_aka = info['title_english']
            rn.year = info['year']
            _log.debug('Release name updated: %s', rn)
            for cb in self._release_name_update_callbacks:
                cb(rn)

        asyncio.ensure_future(fetch_info(id, db))

    def on_release_name_updated(self, callback):
        self._release_name_update_callbacks.append(callback)
