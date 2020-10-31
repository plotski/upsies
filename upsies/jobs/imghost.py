import asyncio

from .. import errors
from ..tools import imghost
from ..utils import daemon
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ImageHostJob(JobBase):
    name = 'imghost'
    label = 'Image URLs'

    @property
    def cache_file(self):
        # No cache file since we may not know which files we're going to upload
        # before execution. This is not a problem because the abstract base
        # class for image uploaders implements caching.
        return None

    def initialize(self, imghost_name, image_paths=(), images_total=0):
        # Accept images from `image_paths` and pipe_input() calls
        if image_paths and images_total:
            raise TypeError('You must not specify both "image_paths" and "images_total".')
        elif not image_paths and not images_total:
            raise TypeError('You must specify "image_paths" or "images_total".')
        else:
            if images_total > 0:
                self._images_total = images_total
            else:
                self._images_total = len(image_paths)

        try:
            imghost_module = getattr(imghost, imghost_name)
        except AttributeError:
            raise ValueError(f'Unknown image hosting service: {imghost_name}')
        else:
            self._imghost = imghost_module.Uploader(cache_dir=self.homedir)

        self._images_uploaded = 0
        self._exit_code = 0
        self._image_path_queue = asyncio.Queue()

        if image_paths:
            for image_path in image_paths:
                self._enqueue(image_path)
            self._close_queue()

        self._upload_task = asyncio.ensure_future(self._upload_images())

    async def _upload_images(self):
        try:
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
                    else:
                        _log.debug('Uploaded image: %r', info)
                        self._images_uploaded += 1
                        self.send(info)
        finally:
            self.finish()

    def _enqueue(self, image_path):
        self._image_path_queue.put_nowait(image_path)

    def _close_queue(self):
        self._image_path_queue.put_nowait(None)

    def pipe_input(self, image_path):
        self._enqueue(image_path)

    def pipe_closed(self):
        self._close_queue()

    def execute(self):
        pass

    def finish(self):
        super().finish()

    async def wait(self):
        try:
            await self._upload_task
        except asyncio.CancelledError:
            self._exit_code = 1
        await super().wait()

    @property
    def exit_code(self):
        if self.is_finished:
            return self._exit_code

    @property
    def images_uploaded(self):
        return self._images_uploaded

    @property
    def images_total(self):
        return self._images_total
