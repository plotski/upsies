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

    default_config = {
        # Use smallest thumbnail size
        'thumb_width': 0,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._gallery = pyimgbox.Gallery(
            thumb_width=self.config['thumb_width'],
            square_thumbs=False,
            comments_enabled=False,
        )

    async def _upload(self, image_path):
        submission = await self._gallery.upload(image_path)
        _log.debug('Submission: %r', submission)
        if not submission.success:
            raise errors.RequestError(submission.error)
        else:
            return {
                'url': submission.image_url,
                'thumbnail_url': submission.thumbnail_url,
                'edit_url': submission.edit_url,
            }
