"""
Upload images to image hosting services
"""

from .. import errors
from ..utils.imghosts import ImageHostBase
from . import QueueJobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ImageHostJob(QueueJobBase):
    """Upload images to an image hosting service"""

    name = 'imghost'
    label = 'Image URLs'

    # Don't cache output and rely on caching in ImageHostBase. Otherwise, a
    # single failed/cancelled upload would throw away all the gathered URLs.
    cache_id = None

    def initialize(self, *, imghost, images_total=0, enqueue=()):
        """
        Validate arguments and set internal state

        :param ImageHostBase imghost: Return value of
            :func:`.utils.imghosts.imghost`
        :param enqueue: Sequence of image paths (see
            :class:`~.base.QueueJobBase`)
        :param images_total: Number of images that are going to be uploaded. The
            only purpose of this value is to provide it via the :attr:`images_total`
            property to calculate progress.

        If `enqueue` is given, the job finishes after all images are uploaded.

        If `enqueue` is not given, calls to :meth:`upload` are expected and
        :meth:`finalize` must be called after the last call.

        `enqueue` and `images_total` must not be given at the same time.
        """
        if enqueue and images_total:
            raise RuntimeError('You must not give both arguments "enqueue" and "images_total".')
        else:
            assert isinstance(imghost, ImageHostBase), f'Not an ImageHostBase: {imghost!r}'
            imghost.cache_directory = self.cache_directory
            self._imghost = imghost
            self._images_uploaded = 0
            self._uploaded_images = []
            if images_total > 0:
                self.images_total = images_total
            else:
                self.images_total = len(enqueue)

    async def handle_input(self, image_path):
        try:
            info = await self._imghost.upload(image_path, cache=not self.ignore_cache)
        except errors.RequestError as e:
            self.error(e)
        else:
            _log.debug('Uploaded image: %r', info)
            self._images_uploaded += 1
            self._uploaded_images.append(info)
            image_url = str(info)
            self.send(image_url)

    @property
    def exit_code(self):
        """`0` if all images were uploaded, `1` otherwise, `None` if unfinished"""
        if self.is_finished:
            if self.images_uploaded > 0 and self.images_uploaded == self.images_total:
                return 0
            else:
                return 1

    @property
    def uploaded_images(self):
        """
        Sequence of :class:`~.imghosts.common.UploadedImage` objects

        Use this property to get additional information like thumbnail URLs that
        are not part of this job's :attr:`~.base.JobBase.output`.
        """
        return tuple(self._uploaded_images)

    @property
    def images_uploaded(self):
        """Number of uploaded images"""
        return self._images_uploaded

    @property
    def images_total(self):
        """Expected number of images to upload"""
        return self._images_total

    @images_total.setter
    def images_total(self, value):
        self._images_total = int(value)

    def set_images_total(self, value):
        """:attr:`images_total` setter as a method"""
        self.images_total = value
