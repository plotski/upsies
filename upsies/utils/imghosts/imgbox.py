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
    """
    Upload images to a gallery on imgbox.com

    :param int thumb_width: Width of the thumbnails (automatically snaps to
        closest supported value)
    """

    DEFAULT_THUMBNAIL_WIDTH = 300
    name = 'imgbox'

    def __init__(self, *args, thumb_width=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._gallery = pyimgbox.Gallery(
            thumb_width=thumb_width or self.DEFAULT_THUMBNAIL_WIDTH,
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
