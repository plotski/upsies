"""
Image uploader for imgbb.com
"""

import json

from ... import errors
from ...utils import http
from .base import ImageHostBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ImgbbImageHost(ImageHostBase):
    """Upload images to imgbb.com"""

    name = 'imgbb'

    default_config = {
        'base_url': 'https://api.imgbb.com',
        'apikey': '',
    }

    # The file path is unique enough
    cache_id = None

    async def _upload_image(self, image_path):
        try:
            response = await http.post(
                url=f'{self.options["base_url"]}/1/upload',
                cache=False,
                data={
                    'key': self.options['apikey'],
                },
                files={
                    'image': image_path,
                },
            )
        except errors.RequestError as e:
            # Error response is undocumented. I looks like this:
            # {
            #   "status_code": 400,
            #   "error": {
            #     "message": "Can't get target upload source info",
            #     "code": 310,
            #     "context": "CHV\\UploadException"
            #   },
            #   "status_txt": "Bad Request"
            # }
            _log.debug('Error: %r', e.text)
            try:
                info = json.loads(e.text)
                raise errors.RequestError(f'{info["status_txt"]}: {info["error"]["message"]}')
            except (TypeError, ValueError, KeyError):
                raise errors.RequestError(f'Upload failed: {e.text}')

        _log.debug('%s: Response: %r', self.name, response)
        images = response.json()
        try:
            return images['data']['url']
        except KeyError:
            raise RuntimeError(f'Unexpected response: {response}')
