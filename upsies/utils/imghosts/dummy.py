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

    description = (
        'This is a fake image hosting service '
        'that is used for testing and debugging.'
    )

    default_config = {
        'hostname': 'localhost',
    }

    argument_definitions = {
        ('--hostname', '-n'): {
            'help': 'Host name in the dummy URL',
        },
    }

    @property
    def cache_id(self):
        return self.options['hostname']

    async def _upload_image(self, image_path):
        try:
            fs.assert_file_readable(image_path)
        except errors.ContentError as e:
            raise errors.RequestError(e)
        else:
            await asyncio.sleep(1.5)
            url = f'http://{self.options["hostname"]}/{os.path.basename(image_path)}'
            return url
