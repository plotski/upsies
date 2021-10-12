"""
Image uploader for pixhost.to
"""

import json

from ... import errors
from ...utils import http
from .base import ImageHostBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class FreeimageImageHost(ImageHostBase):
    """Upload images to freeimage.host"""

    name = 'freeimage'

    default_config = {
        'base_url': 'https://freeimage.host',
        'apikey': '6d207e02198a847aa98d0a2a901485a5',
    }

    async def _upload(self, image_path):
        try:
            response = await http.post(
                url=self.options['base_url'] + '/api/1/upload',
                cache=False,
                data={
                    'key': self.options['apikey'],
                    'action': 'upload',
                    'format': 'json',
                },
                files={
                    'source': image_path,
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
            try:
                info = json.loads(e.text)
                raise errors.RequestError(f'{info["status_txt"]}: {info["error"]["message"]}')
            except (TypeError, ValueError, KeyError):
                raise errors.RequestError(f'Upload failed: {e.text}')

        _log.debug('%s: Response: %r', self.name, response)
        info = response.json()
        _log.debug('%s: JSON: %r', self.name, info)
        try:
            return {
                'url': info['image']['image']['url'],
                'thumbnail_url': info['image']['medium']['url'],
            }
        except KeyError:
            raise RuntimeError(f'Unexpected response: {response}')
