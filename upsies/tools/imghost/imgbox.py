from ... import errors
from ...utils import LazyModule
from . import UploaderBase

import logging  # isort:skip
_log = logging.getLogger(__name__)

pyimgbox = LazyModule(module='pyimgbox', namespace=globals())


class Uploader(UploaderBase):
    """
    Upload images to a gallery on imgbox.com

    :param int thumb_width: Horizontal width of the thumbnails
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

    def _upload(self, image_path):
        if not self._gallery.created:
            self._gallery.create()
            _log.debug('Created gallery: %r', self._gallery)

        # Gallery.add() is an iterator, but we only upload a single image so we
        # can just return instead of yielding.
        for submission in self._gallery.add(image_path):
            _log.debug('Submission: %r', submission)
            if not submission.success:
                raise errors.RequestError(submission.error)
            else:
                return {
                    'url': submission.image_url,
                    'thumb_url': submission.thumbnail_url,
                    'edit_url': submission.edit_url,
                }
