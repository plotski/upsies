import os
import queue

import natsort

from .. import errors, tools
from ..utils import timestamp, video
from . import _base, _common

import logging  # isort:skip
_log = logging.getLogger(__name__)

DEFAULT_NUMBER_OF_SCREENSHOTS = 2


class ScreenshotsJob(_base.JobBase):
    name = 'screenshots'
    label = 'Screenshots'

    @property
    def cache_file(self):
        return os.path.join(
            self.cache_directory,
            f'{self.name}:{",".join(self._timestamps)}.json',
        )

    def initialize(self, content_path, timestamps=(), number=0, upload_to=None):
        self._video_file = video.first_video(content_path)
        self._timestamps = _screenshot_timestamps(
            video_file=self._video_file,
            timestamps=timestamps,
            number=number,
        )
        self._screenshots_created = 0
        self._screenshots_wanted = len(self._timestamps)
        self._screenshot_filepaths = []
        if not self._screenshots_wanted > 0:
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
            name=self.name,
            target=_screenshot_process,
            kwargs={
                'video_file' : self._video_file,
                'timestamps' : self._timestamps,
                'output_dir' : self.homedir,
                'overwrite'  : self.ignore_cache,
            },
            info_callback=self.handle_screenshot_path,
            error_callback=self.handle_screenshot_error,
            finished_callback=self.handle_screenshots_finished,
        )
        self._screenshot_process.start()

        if self._imghost:
            self._upload_thread = _UploadThread(
                homedir=self.homedir,
                imghost=self._imghost,
                force=self.ignore_cache,
                url_callback=self.handle_upload_url,
                error_callback=self.handle_upload_error,
                finished_callback=self.handle_uploads_finished,
            )
            self._upload_thread.start()

    def finish(self):
        if hasattr(self, '_screenshot_process'):
            self._screenshot_process.stop()
        if hasattr(self, '_upload_thread'):
            self._upload_thread.stop()
        super().finish()

    async def wait(self):
        if hasattr(self, '_screenshot_process'):
            await self._screenshot_process.join()
        if hasattr(self, '_upload_thread'):
            await self._upload_thread.join()
        await super().wait()

    @property
    def exit_code(self):
        if self.is_finished:
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

    def on_screenshot_path(self, callback):
        self._screenshot_path_callbacks.append(callback)

    def handle_screenshot_path(self, path):
        _log.debug('New screenshot: %r', path)
        self._screenshots_created += 1
        self._screenshot_filepaths.append(path)
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
            cb(tuple(self._screenshot_filepaths))

    @property
    def is_uploading(self):
        return self._imghost is not None
        # return hasattr(self, '_upload_thread')

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


def _screenshot_timestamps(video_file, timestamps, number):
    total_secs = video.length(video_file)

    timestamps_pretty = []
    for ts in timestamps:
        ts = max(0, min(total_secs, timestamp.parse(ts)))
        timestamps_pretty.append(timestamp.pretty(ts))

    if not timestamps and not number:
        number = DEFAULT_NUMBER_OF_SCREENSHOTS

    # Add more timestamps if the user didn't specify enough
    if number > 0 and len(timestamps_pretty) < number:
        # Convert timestamp strings to seconds
        timestamps = sorted(timestamp.parse(ts) for ts in timestamps_pretty)

        # Fractions of total video length
        positions = [ts / total_secs for ts in timestamps]

        # Include start and end of video
        if 0.0 not in positions:
            positions.insert(0, 0.0)
        if 1.0 not in positions:
            positions.append(1.0)

        # Insert timestamps between the two with the largest distance
        while len(timestamps_pretty) < number:
            pairs = [(a, b) for a, b in zip(positions, positions[1:])]
            max_distance, pos1, pos2 = max((b - a, a, b) for a, b in pairs)
            position = ((pos2 - pos1) / 2) + pos1
            timestamps_pretty.append(timestamp.pretty(total_secs * position))
            positions.append(position)
            positions.sort()

    return natsort.natsorted(timestamps_pretty)


def _screenshot_process(output_queue, input_queue,
                        video_file, timestamps, output_dir, overwrite):
    for ts in timestamps:
        screenshot_file = os.path.join(
            output_dir,
            os.path.basename(video_file) + f'.{ts}.png',
        )
        try:
            tools.screenshot.create(
                video_file=video_file,
                timestamp=ts,
                screenshot_file=screenshot_file,
                overwrite=overwrite,
            )
        except (ValueError, errors.ScreenshotError) as e:
            output_queue.put((_common.DaemonProcess.ERROR, str(e)))
        else:
            output_queue.put((_common.DaemonProcess.INFO, screenshot_file))


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
