import asyncio

from . import ClientApiBase

class ClientApi(ClientApiBase):
    """Dummy client API for testing and debugging"""

    name = 'dummy'

    async def add_torrent(self, torrent_path, download_path=None):
        await asyncio.sleep(0.5)
        return '123'
