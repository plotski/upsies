"""
Image uploader for imgbox.com
"""

from ... import errors
from .. import LazyModule
from .base import ImageHostBase

import logging  # isort:skip
_log = logging.getLogger(__name__)

pyimgbox = LazyModule(module='pyimgbox', namespace=globals())


class ImgboxImageHost(ImageHostBase):
    """Upload images to a gallery on imgbox.com"""

    name = 'imgbox'

    async def _upload_image(self, image_path):
        gallery = pyimgbox.Gallery(
            thumb_width=self.options['thumb_width'],
            square_thumbs=False,
            comments_enabled=False,
        )
        try:
            submission = await gallery.upload(image_path)
            _log.debug('Submission: %r', submission)
            if not submission.success:
                raise errors.RequestError(submission.error)
            else:
                return submission.image_url
        finally:
            await gallery.close()
