"""
Image uploader for imgbb.com
"""

import json

from ... import __project_name__, constants, errors
from ...utils import configfiles, fs, http
from .base import ImageHostBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ImgbbImageHost(ImageHostBase):
    """Upload images to imgbb.com"""

    name = 'imgbb'

    default_config = {
        'base_url': 'https://api.imgbb.com',
        'apikey': configfiles.config_value(
            value='',
            description=(
                f'Run ``{__project_name__} ui {name} -h`` '
                'for instructions on how to get an API key.'
            ),
        ),
    }

    description = (
        'You need an API key to upload images. You can get one by following these steps:\n'
        '\n'
        '  1. Create an account: https://imgbb.com/signup\n'
        '  2. Go to https://api.imgbb.com/ and click on "Get API key".\n'
        f'  3. Store your API key in {fs.tildify_path(constants.IMGHOSTS_FILEPATH)}:\n'
        '\n'
        f'       $ {__project_name__} set imghosts.imgbb.apikey <YOUR API KEY>'
    )

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
