import asyncio
import os

from . import SubmitJobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmitJob(SubmitJobBase):
    tracker_name = 'DUMMY'

    async def login(self, http_session):
        asyncio.sleep(1)

    async def logout(self, http_session):
        asyncio.sleep(0.5)

    async def upload(self, http_session):
        _log.debug('Submission metadata: %r', self.metadata)
        torrent_file = self.metadata['create-torrent'][0]
        return f'http://localhost/{os.path.basename(torrent_file)}'
