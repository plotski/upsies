import os

from .. import errors, tools
from ..utils import LazyModule, daemon, fs, timestamp, video
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)

DEFAULT_NUMBER_OF_SCREENSHOTS = 2

natsort = LazyModule(module='natsort', namespace=globals())


class ScreenshotsJob(JobBase):
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
        if not self._screenshots_total > 0:
            raise RuntimeError('No screenshots wanted?')
        self._screenshot_process = daemon.DaemonProcess(
            name=self.name,
            target=_screenshot_process,
            kwargs={
                'video_file' : self._video_file,
                'timestamps' : self._timestamps,
                'output_dir' : self.homedir,
                'overwrite'  : self.ignore_cache,
            },
            info_callback=self.handle_screenshot,
            error_callback=self.error,
            finished_callback=self.finish,
        )

    def execute(self):
        self._screenshot_process.start()

    def finish(self):
        self._screenshot_process.stop()
        super().finish()

    async def wait(self):
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

    def handle_screenshot(self, path):
        self._screenshots_created += 1
        self.send(path)


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
            output_queue.put((daemon.DaemonProcess.ERROR, str(e)))
        else:
            output_queue.put((daemon.DaemonProcess.INFO, screenshot_file))
