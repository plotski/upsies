import os

from .. import errors, tools
from ..utils import LazyModule, fs, timestamp, video
from . import _base, _common

import logging  # isort:skip
_log = logging.getLogger(__name__)

DEFAULT_NUMBER_OF_SCREENSHOTS = 2

natsort = LazyModule(module='natsort', namespace=globals())


class ScreenshotsJob(_base.JobBase):
    name = 'screenshots'
    label = 'Screenshots'

    @property
    def cache_file(self):
        filename = f'{self.name}.{",".join(self._timestamps)}.json'
        return os.path.join(self.cache_directory, filename)

    def initialize(self, content_path, timestamps=(), number=0):
        self._video_file = video.first_video(content_path)
        self._timestamps = _screenshot_timestamps(
            video_file=self._video_file,
            timestamps=timestamps,
            number=number,
        )
        self._screenshots_created = 0
        self._screenshots_total = len(self._timestamps)
        self._screenshot_filepaths = []
        if not self._screenshots_total > 0:
            raise RuntimeError('No screenshots wanted?')

        self._screenshot_path_callbacks = []
        self._screenshot_error_callbacks = []
        self._screenshots_finished_callbacks = []

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

    def finish(self):
        if hasattr(self, '_screenshot_process'):
            self._screenshot_process.stop()
        super().finish()

    async def wait(self):
        if hasattr(self, '_screenshot_process'):
            await self._screenshot_process.join()
        await super().wait()

    @property
    def exit_code(self):
        if self.is_finished:
            return 0 if len(self.output) == self.screenshots_total else 1

    @property
    def screenshots_total(self):
        return self._screenshots_total

    @property
    def screenshots_created(self):
        return self._screenshots_created

    def on_screenshot_path(self, callback):
        self._screenshot_path_callbacks.append(callback)

    def handle_screenshot_path(self, path):
        _log.debug('New screenshot: %r', path)
        self._screenshots_created += 1
        self._screenshot_filepaths.append(path)
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
        self.finish()
        for cb in self._screenshots_finished_callbacks:
            cb(tuple(self._screenshot_filepaths))


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
            fs.basename(video_file) + f'.{ts}.png',
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
