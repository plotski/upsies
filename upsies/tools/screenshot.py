import errno
import os
import re

from .. import binaries, errors
from ..utils import run
from ..utils import timestamp as ts
from ..utils import video

import logging  # isort:skip
_log = logging.getLogger(__name__)

_timestamp_format = re.compile(r'^(?:(?:\d+:|)\d{2}:|)\d{2}$')


def _make_ffmpeg_cmd(videofile, timestamp, screenshotfile):
    return (
        binaries.ffmpeg,
        '-y',
        '-loglevel', 'level+error',
        '-ss', str(timestamp),
        '-i', video.make_ffmpeg_input(videofile),
        '-vframes', '1',
        # Use correct aspect ratio
        # https://ffmpeg.org/ffmpeg-filters.html#toc-Examples-99
        '-vf', 'scale=trunc(ih*dar):ih,setsar=1/1',
        f'file:{screenshotfile}',
    )


def create(videofile, timestamp, screenshotfile):
    """
    Create screenshot from video file

    :param str videofile: Path to video file
    :param timestamp: Time location in the video
    :type timestamp: int or float or "[[H+:]MM:]SS"
    :param str screenshotfile: Path to screenshot file

    :raise FileNotFoundError: if `videofile` doesn't exist
    :raise ValueError: if `timestamp` is of unexpected type or format
    """
    if not os.path.exists(videofile):
        raise FileNotFoundError(f'{videofile}: {os.strerror(errno.ENOENT)}')

    if isinstance(timestamp, str):
        if not _timestamp_format.match(timestamp):
            raise ValueError(f'Invalid timestamp: {timestamp!r}')
    elif not isinstance(timestamp, (int, float)):
        raise ValueError(f'Invalid timestamp: {timestamp!r}')

    if os.path.exists(screenshotfile):
        _log.debug('Screenshot already exists: %s', screenshotfile)
        return

    videolength = video.length(videofile)
    if videolength <= ts.parse(timestamp):
        raise ValueError(f'Timestamp is after video end ({ts.pretty(videolength)}): '
                         f'{ts.pretty(timestamp)}')

    cmd = _make_ffmpeg_cmd(videofile, timestamp, screenshotfile)
    output = run.run(cmd, ignore_stderr=True, join_output=True)
    if not os.path.exists(screenshotfile):
        raise errors.ScreenshotError(output, videofile, timestamp)
