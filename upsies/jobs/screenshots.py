"""
Create screenshots from video file(s)
"""

import os
import queue

from .. import errors
from ..utils import LazyModule, daemon, fs, screenshot, timestamp, video
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)

DEFAULT_NUMBER_OF_SCREENSHOTS = 2

natsort = LazyModule(module='natsort', namespace=globals())


class ScreenshotsJob(JobBase):
    """
    Create screenshots

    :param str content_path: Path to file or directory (filtered through
        :func:`~.video.first_video`)
    :param timestamps: Positions in the video to make screenshots at
    :type timestamps: sequence of "[[H+:]M+:]S+" strings or seconds
    :param number: How many screenshots to make

    If `timestamps` and `number` are not given, screenshot positions are picked
    at even intervals.

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``video_file``
            Emitted after the video file to take screenshots from is determined.
            Registered callbacks get the path to the video file as a positional
            argument.

        ``timestamps``
            Emitted after the screenshot timestamps are determined. Registered
            callbacks get the list of timestamps in the form of "H+:MM:SS" as a
            positional argument.
    """

    name = 'screenshots'
    label = 'Screenshots'

    def initialize(self, content_path, timestamps=(), number=0):
        self._screenshots_created = 0
        self._screenshots_total = -1
        self._video_file = ''
        self._timestamps = ()
        self.signal.add('video_file')
        self.signal.add('timestamps')
        self._screenshots_process = daemon.DaemonProcess(
            name=self.name,
            target=_screenshots_process,
            kwargs={
                'content_path' : content_path,
                'timestamps'   : timestamps,
                'number'       : number,
                'output_dir'   : self.homedir,
                'overwrite'    : self.ignore_cache,
            },
            info_callback=self.handle_info,
            error_callback=self.handle_error,
            finished_callback=self.finish,
        )

    def execute(self):
        self._screenshots_process.start()

    def finish(self):
        self._screenshots_process.stop()
        super().finish()

    async def wait(self):
        await self._screenshots_process.join()
        await super().wait()

    def handle_info(self, info):
        if not self.is_finished:
            if info[0] == 'video_file':
                self._video_file = info[1]
                self.signal.emit('video_file', self._video_file)
            elif info[0] == 'timestamps':
                self._timestamps = tuple(info[1])
                self._screenshots_total = len(self._timestamps)
                self.signal.emit('timestamps', self._timestamps)
            elif info[0] == 'screenshot':
                self._screenshots_created += 1
                self.send(info[1])

    def handle_error(self, error):
        if not self.is_finished:
            self.error(error)
            self.finish()

    @property
    def exit_code(self):
        if self.is_finished:
            if self.screenshots_total < 0:
                # Job is finished but _screenshots_process() never sent us
                # timestamps. That means we're either using previously cached
                # output or the job was cancelled while _screenshots_process()
                # was still initializing.
                if self.output:
                    # Assume the cached number of screenshots is what the user
                    # wanted because the output of unsuccessful jobs is not
                    # cached (see JobBase._write_output_cache()).
                    return 0
                else:
                    return 1
            elif len(self.output) == self.screenshots_total:
                return 0
            else:
                return 1

    @property
    def video_file(self):
        """
        Path to video file screenshots are taken from

        .. note:: This is an empty string before the the ``video_file``
                  :attr:`~.JobBase.signal` is emitted.
        """
        return self._video_file

    @property
    def timestamps(self):
        """
        List of normalized and validated human-readable timestamps

        .. note:: This is an empty sequence before the ``timestamps``
                  :attr:`~.JobBase.signal` is emitted.
        """
        return self._timestamps

    @property
    def screenshots_total(self):
        """
        Total number of screenshots to make

        .. note:: This is an empty sequence before the ``timestamps``
                  :attr:`~.JobBase.signal` is emitted.
        """
        return self._screenshots_total

    @property
    def screenshots_created(self):
        """Total number of screenshots made so far"""
        return self._screenshots_created


def _normalize_timestamps(video_file, timestamps, number):
    """
    Return list of human-readable time stamps

    :params video_file: Path to video file
    :parms timestamps: Sequence of arguments for :func:`~utils.timestamp.parse`
    :parms int number: Desired number of timestamps

    :raise ValueError: if an item in `timestamps` is invalid
    :raise ContentError: if `video_file` is not a video file
    """
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


def _screenshots_process(output_queue, input_queue,
                         content_path, timestamps, number, output_dir, overwrite):
    # Find appropriate video file if `content_path` is a directory
    try:
        video_file = video.first_video(content_path)
    except errors.ContentError as e:
        output_queue.put((daemon.MsgType.error, str(e)))
    else:
        if _shall_terminate(input_queue):
            return

        # Report video_file
        output_queue.put((daemon.MsgType.info, ('video_file', video_file)))

        # Get list of valid timestamps based on fixed timestamps and desired
        # amount of screenshots
        try:
            timestamps = _normalize_timestamps(
                video_file=video_file,
                timestamps=timestamps,
                number=number,
            )
        except (ValueError, errors.ContentError) as e:
            output_queue.put((daemon.MsgType.error, str(e)))
        else:
            # Report valid timestamps
            output_queue.put((daemon.MsgType.info, ('timestamps', timestamps)))

            for ts in timestamps:
                if _shall_terminate(input_queue):
                    return

                screenshot_file = os.path.join(
                    output_dir,
                    fs.basename(video_file) + f'.{ts}.png',
                )
                try:
                    screenshot.create(
                        video_file=video_file,
                        screenshot_file=screenshot_file,
                        timestamp=ts,
                        overwrite=overwrite,
                    )
                except errors.ScreenshotError as e:
                    output_queue.put((daemon.MsgType.error, str(e)))
                else:
                    output_queue.put((daemon.MsgType.info, ('screenshot', screenshot_file)))


def _shall_terminate(input_queue):
    try:
        typ, msg = input_queue.get_nowait()
    except queue.Empty:
        pass
    else:
        if typ == daemon.MsgType.terminate:
            return True
    return False
