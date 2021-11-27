"""
Image uploader for freeimage.host
"""

import json

from ... import errors, utils
from .base import ImageHostBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class FreeimageImageHost(ImageHostBase):
    """Upload images to freeimage.host"""

    name = 'freeimage'

    default_config = {
        'base_url': 'https://freeimage.host',
        'apikey': utils.configfiles.config_value(
            value='6d207e02198a847aa98d0a2a901485a5',
            description='The default value is the public API key from https://freeimage.host/page/api.',
        ),
    }

    async def _upload_image(self, image_path):
        try:
            response = await utils.http.post(
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
        try:
            return info['image']['image']['url']
        except KeyError:
            raise RuntimeError(f'Unexpected response: {response}')
