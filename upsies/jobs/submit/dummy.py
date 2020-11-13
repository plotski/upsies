import asyncio
import os

from . import SubmitJobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmitJob(SubmitJobBase):
    tracker_name = 'DUMMY'

    async def login(self):
        await asyncio.sleep(1)

    async def logout(self):
        await asyncio.sleep(0.5)

    async def upload(self):
        # create-torrent output could be empty sequence or None
        output = self.metadata.get('create-torrent')
        if output:
            torrent_file = output[0]
            return f'http://localhost/{os.path.basename(torrent_file)}'
