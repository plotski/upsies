import asyncio

from .. import errors
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ImageHostJob(JobBase):
    """
    Upload images to an image hosting service

    :param str imghost: Return value of :func:`tools.imghost.imghost`
    :param image_paths: Sequence of paths to image files
    :param images_total: Number of images that are going to be uploaded. The
        only purpose of this value is to provide it via the :attr:`images_total`
        property to calculate progress.

    If image_paths is given, the job finishes after all images are uploaded.

    If image_patahs is not given, calls to :meth:`upload` are expected and
    :meth:`finalize` must be called after the last call.

    `image_paths` and `images_total` must not be given at the same time.
    """

    name = 'imghost'
    label = 'Image URLs'

    @property
    def cache_file(self):
        # No cache file since we may not know which files we're going to upload
        # before execution. This is not a problem because ImageHostBase
        # implements caching.
        return None

    def initialize(self, imghost, image_paths=(), images_total=0):
        # Accept images from `image_paths` and pipe_input() calls
        if image_paths and images_total:
            raise RuntimeError('You must not specify both "image_paths" and "images_total".')
        else:
            if images_total > 0:
                self._images_total = images_total
            else:
                self._images_total = len(image_paths)

        self._imghost = imghost
        self._images_uploaded = 0
        self._exit_code = 0
        self._image_path_queue = asyncio.Queue()

        if image_paths:
            for image_path in image_paths:
                self.upload(image_path)
            self.finalize()

        self._upload_images_task = asyncio.ensure_future(self._upload_images())
        self._upload_images_task.add_done_callback(lambda _: self.finish())

    async def _upload_images(self):
        while True:
            image_path = await self._image_path_queue.get()
            if image_path is None:
                _log.debug('All images uploaded')
                break
            else:
                try:
                    info = await self._imghost.upload(image_path, force=self.ignore_cache)
                except errors.RequestError as e:
                    self._exit_code = 1
                    self.error(e)
                    break
                else:
                    _log.debug('Uploaded image: %r', info)
                    self._images_uploaded += 1
                    self.send(info)

    def upload(self, image_path):
        """Upload `image_path`"""
        self._image_path_queue.put_nowait(image_path)

    def finalize(self):
        """Finish after the current upload is done"""
        self._image_path_queue.put_nowait(None)

    def execute(self):
        pass

    def finish(self):
        self._upload_images_task.cancel()
        super().finish()

    async def wait(self):
        try:
            await self._upload_images_task
        except asyncio.CancelledError:
            self._exit_code = 1
        await super().wait()

    @property
    def exit_code(self):
        if self.is_finished:
            return self._exit_code

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
        self.images_total = value
