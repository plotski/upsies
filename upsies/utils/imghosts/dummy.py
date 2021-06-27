"""
Dummy image uploader for testing and debugging
"""

import asyncio
import os

from ... import errors
from .. import fs
from .base import ImageHostBase


class DummyImageHost(ImageHostBase):
    """Dummy service for testing and debugging"""

    name = 'dummy'

    default_config = {
        'hostname': 'localhost',
    }

    async def _upload(self, image_path):
        try:
            fs.assert_file_readable(image_path)
        except errors.ContentError as e:
            raise errors.RequestError(e)
        else:
            await asyncio.sleep(1.5)
            url = f'http://{self.config["hostname"]}/{os.path.basename(image_path)}'
            return {
                'url': url,
                'thumbnail_url': f'{url}/thumbnail',
            }
