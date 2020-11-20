import asyncio
import os

from . import ImageHostBase


class ImageHost(ImageHostBase):
    """Dummy service for testing and debugging"""

    name = 'dummy'

    async def _upload(self, image_path):
        await asyncio.sleep(1)
        url = f'http://localhost/{os.path.basename(image_path)}'
        return {'url': url}
