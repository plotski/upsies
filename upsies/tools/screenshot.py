import errno
import os
import re

from .. import binaries, errors
from ..utils import subproc
from ..utils import timestamp as ts
from ..utils import video

import logging  # isort:skip
_log = logging.getLogger(__name__)

_timestamp_format = re.compile(r'^(?:(?:\d+:|)\d{2}:|)\d{2}$')


def _make_ffmpeg_cmd(video_file, timestamp, screenshot_file):
    return (
        binaries.ffmpeg,
        '-y',
        '-loglevel', 'level+error',
        '-ss', str(timestamp),
        '-i', video.make_ffmpeg_input(video_file),
        '-vframes', '1',
        # Use correct aspect ratio
        # https://ffmpeg.org/ffmpeg-filters.html#toc-Examples-99
        '-vf', 'scale=trunc(ih*dar):ih,setsar=1/1',
        f'file:{screenshot_file}',
    )


def create(video_file, timestamp, screenshot_file, overwrite=False):
    """
    Create screenshot from video file

    :param str video_file: Path to video file
    :param timestamp: Time location in the video
    :type timestamp: int or float or "[[H+:]MM:]SS"
    :param str screenshot_file: Path to screenshot file
    :param bool overwrite: Whether to overwrite `screenshot_file` if it exists

    :raise FileNotFoundError: if `video_file` doesn't exist
    :raise ValueError: if `timestamp` is of unexpected type or format
    """
    if not os.path.exists(video_file):
        raise FileNotFoundError(f'{video_file}: {os.strerror(errno.ENOENT)}')

    if isinstance(timestamp, str):
        if not _timestamp_format.match(timestamp):
            raise ValueError(f'Invalid timestamp: {timestamp!r}')
    elif not isinstance(timestamp, (int, float)):
        raise ValueError(f'Invalid timestamp: {timestamp!r}')

    if not overwrite and os.path.exists(screenshot_file):
        _log.debug('Screenshot already exists: %s', screenshot_file)
        return

    videolength = video.length(video_file)
    if videolength <= ts.parse(timestamp):
        raise ValueError(f'Timestamp is after video end ({ts.pretty(videolength)}): '
                         f'{ts.pretty(timestamp)}')

    cmd = _make_ffmpeg_cmd(video_file, timestamp, screenshot_file)
    output = subproc.run(cmd, ignore_stderr=True, join_output=True)
    if not os.path.exists(screenshot_file):
        raise errors.ScreenshotError(output, video_file, timestamp)
