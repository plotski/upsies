"""
Image uploader for ptpimg.me
"""

from ... import errors
from .. import http
from .base import ImageHostBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class PtpimgImageHost(ImageHostBase):
    """Upload images to ptpimg.me"""

    name = 'ptpimg'
    _url_base = 'https://ptpimg.me'

    def __init__(self, *args, apikey='', **kwargs):
        super().__init__(*args, **kwargs)
        self._apikey = apikey

    async def _upload(self, image_path):
        if not self._apikey:
            raise errors.RequestError('No API key configured')

        response = await http.post(
            url=f'{self._url_base}/upload.php',
            cache=False,
            headers={
                'referer': f'{self._url_base}/index.php',
            },
            data={
                'api_key': self._apikey,
            },
            files={
                'file-upload[0]': image_path,
            },
        )
        _log.debug('%s: Response: %r', self.name, response)
        images = response.json()
        _log.debug('%s: JSON: %r', self.name, images)

        try:
            code = images[0]['code']
            ext = images[0]['ext']
            assert code and ext, (code, ext)
        except (IndexError, KeyError, TypeError, AssertionError):
            raise RuntimeError(f'Unexpected response: {images}')
        else:
            image_url = f'{self._url_base}/{code}.{ext}'
            return {'url': image_url}
