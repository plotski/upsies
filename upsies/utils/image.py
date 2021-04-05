"""
Dump frames from video file
"""

import os
import re

from .. import errors, utils

import logging  # isort:skip
_log = logging.getLogger(__name__)

_timestamp_format = re.compile(r'^(?:(?:\d+:|)\d{2}:|)\d{2}$')


def _ffmpeg_executable():
    if utils.os_family() == 'windows':
        return 'ffmpeg.exe'
    else:
        return 'ffmpeg'


def _make_screenshot_cmd(video_file, timestamp, screenshot_file):
    return (
        _ffmpeg_executable(),
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

def screenshot(video_file, timestamp, screenshot_file, overwrite=False):
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
        return screenshot_file

    duration = utils.video.duration(video_file)
    if duration <= utils.timestamp.parse(timestamp):
        raise errors.ScreenshotError(
            f'Timestamp is after video end ({utils.timestamp.pretty(duration)}): '
            + utils.timestamp.pretty(timestamp)
        )

    cmd = _make_screenshot_cmd(video_file, timestamp, screenshot_file)
    output = utils.subproc.run(cmd, ignore_errors=True, join_stderr=True)
    if not os.path.exists(screenshot_file):
        raise errors.ScreenshotError(
            f'{video_file}: Failed to create screenshot at {timestamp}: {output}'
        )
    else:
        return screenshot_file


def _make_resize_cmd(image_file, dimensions, resized_file):
    return (
        _ffmpeg_executable(),
        '-y',
        '-loglevel', 'level+error',
        '-i', f'file:{image_file}',
        '-vf', f'scale={dimensions}',
        f'file:{resized_file}',
    )

def resize(image_file, width=None, height=None):
    try:
        utils.fs.assert_file_readable(image_file)
    except errors.ContentError as e:
        raise errors.ImageResizeError(e)

    if width and width < 1:
        raise errors.ImageResizeError(f'Width must be greater than zero: {width}')
    elif height and height < 1:
        raise errors.ImageResizeError(f'Height must be greater than zero: {height}')
    elif width and height:
        dimensions = f'w={int(width)}:h={int(height)}'
    elif width:
        dimensions = f'w={int(width)}:h=-1'
    elif height:
        dimensions = f'w=-1:h={int(height)}'
    else:
        return image_file

    target_path = (
        utils.fs.strip_extension(image_file)
        + '.resized.'
        + utils.fs.file_extension(image_file)
    )
    _log.debug('Resizing to %r: %r', dimensions, image_file)
    _log.debug('Resize target: %r', target_path)

    cmd = _make_resize_cmd(image_file, dimensions, target_path)
    output = utils.subproc.run(cmd, ignore_errors=True, join_stderr=True)
    if not os.path.exists(target_path):
        raise errors.ImageResizeError(
            f'{image_file}: Failed to resize: {output}'
        )
    else:
        return target_path
