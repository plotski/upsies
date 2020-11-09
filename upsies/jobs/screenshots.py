import os
import queue

from .. import errors, tools
from ..utils import LazyModule, daemon, fs, timestamp, video
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)

DEFAULT_NUMBER_OF_SCREENSHOTS = 2

natsort = LazyModule(module='natsort', namespace=globals())


class ScreenshotsJob(JobBase):
    """
    Create screenshots

    :param str content_path: Path to file or directory (see
        :func:`~.video.first_video`)
    :param timestamps: Positions in the video to make screenshots
    :type timestamps: sequence of "[[HH:]MM:]SS" strings or seconds
    :param number: Amount of screenshots to make

    If `timestamps` and `number` are not given, screenshot positions are
    generated.
    """

    name = 'screenshots'
    label = 'Screenshots'

    @property
    def cache_file(self):
        if self._timestamps:
            filename = f'{self.name}.{",".join(self._timestamps)}.json'
            return os.path.join(self.cache_directory, filename)

    def initialize(self, content_path, timestamps=(), number=0):
        self._screenshot_process = None
        self._screenshots_created = 0
        self._screenshots_total = 0
        self._video_file = ''
        self._timestamps = ()

        try:
            self._video_file = video.first_video(content_path)
        except errors.ContentError as e:
            self.handle_error(e)
        else:
            try:
                self._timestamps = _normalize_timestamps(
                    video_file=self._video_file,
                    timestamps=timestamps,
                    number=number,
                )
            # _normalize_timestamp may raise ValueError from utils.timestamp or
            # ContentError from utils.video.length()
            except (ValueError, errors.ContentError) as e:
                self.handle_error(e)

            else:
                self._screenshots_total = len(self._timestamps)
                if self._screenshots_total <= 0:
                    self.finish()
                else:
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
                        error_callback=self.handle_error,
                        finished_callback=self.finish,
                    )

    def execute(self):
        if self._screenshot_process:
            self._screenshot_process.start()

    def finish(self):
        if self._screenshot_process:
            self._screenshot_process.stop()
        super().finish()

    async def wait(self):
        if self._screenshot_process:
            await self._screenshot_process.join()
        await super().wait()

    @property
    def exit_code(self):
        if self.is_finished:
            screenshots_wanted = self.screenshots_total > 0
            wanted_screenshots_created = len(self.output) == self.screenshots_total
            return 0 if screenshots_wanted and wanted_screenshots_created else 1

    @property
    def screenshots_total(self):
        return self._screenshots_total

    @property
    def screenshots_created(self):
        return self._screenshots_created

    def handle_screenshot(self, path):
        if not self.is_finished:
            self._screenshots_created += 1
            self.send(path)

    def handle_error(self, error):
        if not self.is_finished:
            self.error(error)
            self.finish()


def _normalize_timestamps(video_file, timestamps, number):
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
        try:
            typ, msg = input_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if typ == daemon.MsgType.terminate:
                break

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
        except errors.ScreenshotError as e:
            output_queue.put((daemon.MsgType.error, str(e)))
        else:
            output_queue.put((daemon.MsgType.info, screenshot_file))
