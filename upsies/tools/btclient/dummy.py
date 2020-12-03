"""
Dummy client API for testing and debugging
"""

import asyncio

from .base import ClientApiBase


class DummyClientApi(ClientApiBase):
    """Dummy client API for testing and debugging"""

    name = 'dummy'

    async def add_torrent(self, torrent_path, download_path=None):
        """Pretend to add `torrent_path`"""
        await asyncio.sleep(0.5)
        return '123'
