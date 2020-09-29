import queue

from .. import errors
from ..tools import imghost
from . import _base, _common

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ImageHostJob(_base.JobBase):
    name = 'imghost'
    label = 'Upload'

    @property
    def cache_file(self):
        # No cache file since we don't know which files we're going to upload
        # before execution. This is not a problem because the abstract base
        # class for image uploaders implements caching.
        return None

    def initialize(self, image_host, images_total=0):
        _log.debug('Uploading %r images to %r', images_total, image_host)
        self._images_uploaded = 0
        self._images_total = images_total
        self._exit_code = 1
        try:
            self._imghost = getattr(imghost, image_host)
        except AttributeError:
            raise ValueError(f'Unknown image hosting service: {image_host}')
        self._url_callbacks = []
        self._error_callbacks = []
        self._finished_callbacks = []

        self._upload_thread = _UploadThread(
            homedir=self.homedir,
            imghost=self._imghost,
            force=self.ignore_cache,
            url_callback=self.handle_image_url,
            error_callback=self.handle_upload_error,
            finished_callback=self.handle_uploads_finished,
        )

    def execute(self):
        self._upload_thread.start()

    def pipe_input(self, filepath):
        self._upload_thread.upload(filepath)

    def pipe_closed(self):
        # Tell the upload thread to terminate after uploading all currently
        # queued images.
        self._upload_thread.finish()

    async def wait(self):
        # We are finished as soon as the upload thread has uploaded all images.
        await self._upload_thread.join()
        super().finish()
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

    @images_total.setter
    def images_total(self, images_total):
        self._images_total = int(images_total)

    def on_image_url(self, callback):
        self._url_callbacks.append(callback)

    def handle_image_url(self, url):
        self._images_uploaded += 1
        self.send(url, if_not_finished=True)
        for cb in self._url_callbacks:
            cb(url)

    def on_upload_error(self, callback):
        self._error_callbacks.append(callback)

    def handle_upload_error(self, error):
        self.error(error, if_not_finished=True)
        for cb in self._error_callbacks:
            cb(error)

    def on_uploads_finished(self, callback):
        self._finished_callbacks.append(callback)

    def handle_uploads_finished(self):
        self.finish()
        self._exit_code = 0
        for cb in self._finished_callbacks:
            cb(self.output)


class _UploadThread(_common.DaemonThread):
    def __init__(self, homedir, imghost, force,
                 url_callback, error_callback, finished_callback):
        self._homedir = homedir
        self._imghost = imghost
        self._force = force
        self._filepaths_queue = queue.Queue()
        self._url_callback = url_callback
        self._error_callback = error_callback
        self._finished_callback = finished_callback

    def upload(self, filepath):
        self._filepaths_queue.put(filepath)

    def finish(self):
        self._filepaths_queue.put(None)

    def initialize(self):
        self._uploader = self._imghost.Uploader(cache_dir=self._homedir)
        self.unblock()

    def work(self):
        try:
            filepath = self._filepaths_queue.get(timeout=0.1)
        except queue.Empty:
            return True  # Call work() again

        if filepath:
            _log.debug('Uploading %r', filepath)
            try:
                info = self._uploader.upload(filepath, force=self._force)
            except errors.RequestError as e:
                self._error_callback(e)
            else:
                self._url_callback(info)

            return True  # Call work() again
        else:
            _log.debug('Upload queue is empty')
            self.stop()
            self._finished_callback()
