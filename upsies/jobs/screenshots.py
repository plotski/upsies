import os
import queue

import natsort

from .. import errors, tools
from ..utils import timestamp, video
from . import _base, _common

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Screenshots(_base.JobBase):
    name = 'screenshots'
    label = 'Screenshots'

    def initialize(self, content_path, timestamps=(), number=0, upload_to=None):
        self._content_path = content_path
        self._timestamps = timestamps or ()
        self._number = number or 0
        self._screenshots_created = 0
        self._screenshots_wanted = max(self._number, len(self._timestamps))
        if self._screenshots_wanted <= 1:
            raise RuntimeError('No screenshots wanted')

        self._screenshots_uploaded = 0
        if upload_to:
            _log.debug('Uploading screenshots to %r', upload_to)
            try:
                self._imghost = getattr(tools.imghost, upload_to)
            except AttributeError:
                raise ValueError(f'Unknown image hosting service: {upload_to}')
        else:
            self._imghost = None

        self._screenshot_path_callbacks = []
        self._screenshot_error_callbacks = []
        self._screenshots_finished_callbacks = []
        self._upload_url_callbacks = []
        self._upload_error_callbacks = []
        self._uploads_finished_callbacks = []

    def execute(self):
        self._screenshot_process = _common.DaemonProcess(
            target=_screenshot_process,
            kwargs={
                'video_file' : video.first_video(self._content_path),
                'timestamps' : self._timestamps,
                'number'     : self._number,
                'output_dir' : self.homedir,
            },
            info_callback=self.handle_screenshot_path,
            error_callback=self.handle_screenshot_error,
            finished_callback=self.handle_screenshots_finished,
        )
        self._screenshot_process.start()

        if self._imghost:
            self._upload_thread = UploadThread(
                imghost=self._imghost,
                url_callback=self.handle_upload_url,
                error_callback=self.handle_upload_error,
                finished_callback=self.handle_uploads_finished,
            )
            _log.debug('Starting upload thread: %r', self._upload_thread)
            self._upload_thread.start()

    def finish(self):
        if hasattr(self, '_screenshot_process'):
            self._screenshot_process.stop()
        if hasattr(self, '_upload_thread'):
            self._upload_thread.stop()
        super().finish()

    async def wait(self):
        _log.debug('Waiting for %r', self)
        if hasattr(self, '_screenshot_process'):
            await self._screenshot_process.join()
        if hasattr(self, '_upload_thread'):
            await self._upload_thread.join()
        await super().wait()

    @property
    def exit_code(self):
        return 0 if len(self.output) == self.screenshots_wanted else 1

    @property
    def screenshots_wanted(self):
        return self._screenshots_wanted

    @property
    def screenshots_created(self):
        return self._screenshots_created

    @property
    def screenshots_uploaded(self):
        return self._screenshots_uploaded

    @property
    def is_uploading(self):
        return hasattr(self, '_upload_thread')

    def on_screenshot_path(self, callback):
        self._screenshot_path_callbacks.append(callback)

    def handle_screenshot_path(self, path):
        _log.debug('New screenshot: %r', path)
        self._screenshots_created += 1
        if self.is_uploading:
            self._upload_thread.upload(path)
        else:
            self.send(path, if_not_finished=True)
        for cb in self._screenshot_path_callbacks:
            cb(path)

    def on_screenshot_error(self, callback):
        self._screenshot_error_callbacks.append(callback)

    def handle_screenshot_error(self, msg):
        self.error(msg, if_not_finished=True)
        for cb in self._screenshot_error_callbacks:
            cb(msg)

    def on_screenshots_finished(self, callback):
        self._screenshots_finished_callbacks.append(callback)

    def handle_screenshots_finished(self):
        if self.is_uploading:
            # Tell upload thread that this is the end
            self._upload_thread.finish()
        else:
            self.finish()
        for cb in self._screenshots_finished_callbacks:
            cb(self.output)

    def on_upload_url(self, callback):
        self._upload_url_callbacks.append(callback)

    def handle_upload_url(self, url):
        self._screenshots_uploaded += 1
        self.send(url, if_not_finished=True)
        for cb in self._upload_url_callbacks:
            cb(url)

    def on_upload_error(self, callback):
        self._upload_error_callbacks.append(callback)

    def handle_upload_error(self, error):
        self.error(error, if_not_finished=True)
        for cb in self._upload_error_callbacks:
            cb(error)

    def on_uploads_finished(self, callback):
        self._uploads_finished_callbacks.append(callback)

    def handle_uploads_finished(self):
        self.finish()
        for cb in self._uploads_finished_callbacks:
            cb(self.output)


def _screenshot_process(output_queue, input_queue,
                        video_file, timestamps, number, output_dir):
    timestamps = _screenshot_timestamps(output_queue, video_file, timestamps, number)
    for ts in timestamps:
        screenshotfile = os.path.join(
            output_dir,
            os.path.basename(video_file) + f'.{ts}.png',
        )
        try:
            tools.screenshot.create(video_file, ts, screenshotfile)
        except (ValueError, errors.ScreenshotError) as e:
            output_queue.put_nowait((_common.DaemonProcess.ERROR, str(e)))
        else:
            output_queue.put_nowait((_common.DaemonProcess.INFO, screenshotfile))


def _screenshot_timestamps(output_queue, video_file, timestamps, number):
    timestamps_pretty = []
    for ts in timestamps:
        try:
            timestamps_pretty.append(timestamp.pretty(ts))
        except (ValueError, TypeError) as e:
            output_queue.put_nowait((_common.DaemonProcess.ERROR, str(e)))

    # If the user didn't specify enough timestamps, add more until we have
    # `number` timestamps.
    if number > 0 and len(timestamps_pretty) < number:
        try:
            total_secs = video.length(video_file)
        except Exception as e:
            output_queue.put_nowait((_common.DaemonProcess.ERROR, str(e)))
            return
        else:
            # Ignore first minute
            offset = 60
            missing = number - len(timestamps_pretty)
            interval = int(total_secs - offset) / (missing + 1)
            for i in range(1, missing + 1):
                ts = timestamp.pretty(offset + (i * interval))
                timestamps_pretty.append(ts)
    return natsort.natsorted(timestamps_pretty)


class UploadThread(_common.DaemonThread):
    def __init__(self, imghost, url_callback, error_callback, finished_callback):
        self._imghost = imghost
        self._filepaths_queue = queue.Queue()
        self._url_callback = url_callback
        self._error_callback = error_callback
        self._finished_callback = finished_callback

    def upload(self, filepath):
        self._filepaths_queue.put_nowait(filepath)

    def finish(self):
        self._filepaths_queue.put_nowait(None)

    def initialize(self):
        self._uploader = self._imghost.Uploader()
        self.unblock()

    def work(self):
        try:
            filepath = self._filepaths_queue.get(timeout=0.1)
        except queue.Empty:
            return True  # Call work() again

        if filepath:
            _log.debug('Uploading %r', filepath)
            try:
                info = self._uploader.upload(filepath)
            except errors.RequestError as e:
                self._error_callback(e)
            else:
                self._url_callback(info)

            return True  # Call work() again
        else:
            _log.debug('Upload queue is empty')
            self.stop()
            self._finished_callback()
