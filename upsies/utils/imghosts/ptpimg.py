"""
Image uploader for ptpimg.me
"""

from ... import errors
from .. import html, http
from .base import ImageHostBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class PtpimgImageHost(ImageHostBase):
    """Upload images to ptpimg.me"""

    name = 'ptpimg'

    default_config = {
        'apikey': '',
        'base_url': 'https://ptpimg.me',
    }

    async def _upload(self, image_path):
        if not self.config['apikey']:
            raise errors.RequestError('Missing API key')

        response = await http.post(
            url=f'{self.config["base_url"]}/upload.php',
            cache=False,
            headers={
                'referer': f'{self.config["base_url"]}/index.php',
            },
            data={
                'api_key': self.config['apikey'],
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
            image_url = f'{self.config["base_url"]}/{code}.{ext}'
            return {'url': image_url}

    async def get_apikey(self, email, password):
        """
        Get API key from website

        :param str email: Email address to use for login
        :param str password: Password to use for login

        :raises RequestError: if getting the HTML fails for some reason

        :return: API key
        """
        _log.debug('Getting API key for %r', email)
        response = await http.post(
            url=f'{self.config["base_url"]}/login.php',
            cache=False,
            data={
                'email': email,
                'pass': password,
                'login': '',
            },
        )

        try:
            soup = html.parse(response)
            _log.debug('%s: %s', self.name, soup.prettify())

            # Find API key
            input_tag = soup.find('input', id='api_key')
            if input_tag:
                return input_tag['value']

            # Find error message
            error_tag = soup.find(class_='panel-body')
            if error_tag:
                raise errors.RequestError(''.join(error_tag.strings).strip())

            # Default exception
            raise RuntimeError('Failed to find API key')
        finally:
            await http.get(f'{self.config["base_url"]}/logout.php')
