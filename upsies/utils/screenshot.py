"""
Dump frames from video file
"""

import os
import re

from .. import errors, utils

import logging  # isort:skip
_log = logging.getLogger(__name__)

if utils.os_family() == 'windows':
    _ffmpeg_executable = 'ffmpeg.exe'
else:
    _ffmpeg_executable = 'ffmpeg'

_timestamp_format = re.compile(r'^(?:(?:\d+:|)\d{2}:|)\d{2}$')


def _make_ffmpeg_cmd(video_file, timestamp, screenshot_file):
    return (
        _ffmpeg_executable,
        '-y',
        '-loglevel', 'level+error',
        '-ss', str(timestamp),
        '-i', utils.video.make_ffmpeg_input(video_file),
        '-vframes', '1',
        # Use correct aspect ratio
        # https://ffmpeg.org/ffmpeg-filters.html#toc-Examples-99
        '-vf', 'scale=trunc(ih*dar):ih,setsar=1/1',
        f'file:{screenshot_file}',
    )


def create(video_file, timestamp, screenshot_file, overwrite=False):
    """
    Create single screenshot from video file

    :param str video_file: Path to video file
    :param timestamp: Time location in the video
    :type timestamp: int or float or "[[H+:]MM:]SS"
    :param str screenshot_file: Path to screenshot file
    :param bool overwrite: Whether to overwrite `screenshot_file` if it exists

    :raise ScreenshotError: if something goes wrong
    """
    try:
        utils.fs.assert_file_readable(video_file)
    except errors.ContentError as e:
        raise errors.ScreenshotError(e)

    if isinstance(timestamp, str):
        if not _timestamp_format.match(timestamp):
            raise errors.ScreenshotError(f'Invalid timestamp: {timestamp!r}')
    elif not isinstance(timestamp, (int, float)):
        raise errors.ScreenshotError(f'Invalid timestamp: {timestamp!r}')

    if not overwrite and os.path.exists(screenshot_file):
        _log.debug('Screenshot already exists: %s', screenshot_file)
        return

    duration = utils.video.duration(video_file)
    if duration <= utils.timestamp.parse(timestamp):
        raise errors.ScreenshotError(
            f'Timestamp is after video end ({utils.timestamp.pretty(duration)}): '
            + utils.timestamp.pretty(timestamp)
        )

    cmd = _make_ffmpeg_cmd(video_file, timestamp, screenshot_file)
    output = utils.subproc.run(cmd, ignore_errors=True, join_stderr=True)
    if not os.path.exists(screenshot_file):
        raise errors.ScreenshotError(output, video_file, timestamp)
