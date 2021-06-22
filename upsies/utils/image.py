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
    # ffmpeg's "image2" image file muxer uses "%" for string formatting
    screenshot_file = str(screenshot_file).replace('%', '%%')
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
    :return: Path to screenshot file
    """
    # See if file is readable before we do further checks and launch ffmpeg
    try:
        utils.fs.assert_file_readable(video_file)
    except errors.ContentError as e:
        raise errors.ScreenshotError(e)

    # Validate timestamps
    if isinstance(timestamp, str):
        if not _timestamp_format.match(timestamp):
            raise errors.ScreenshotError(f'Invalid timestamp: {timestamp!r}')
    elif not isinstance(timestamp, (int, float)):
        raise errors.ScreenshotError(f'Invalid timestamp: {timestamp!r}')

    # Check for previously created screenshot
    if not overwrite and os.path.exists(screenshot_file):
        _log.debug('Screenshot already exists: %s', screenshot_file)
        return screenshot_file

    # Ensure timestamp is within range
    try:
        duration = utils.video.duration(video_file)
    except errors.ContentError as e:
        raise errors.ScreenshotError(e)
    else:
        if duration <= utils.timestamp.parse(timestamp):
            raise errors.ScreenshotError(
                f'Timestamp is after video end ({utils.timestamp.pretty(duration)}): '
                + utils.timestamp.pretty(timestamp)
            )

    # Make screenshot
    cmd = _make_screenshot_cmd(video_file, timestamp, screenshot_file)
    output = utils.subproc.run(cmd, ignore_errors=True, join_stderr=True)
    if not os.path.exists(screenshot_file):
        raise errors.ScreenshotError(
            f'{video_file}: Failed to create screenshot at {timestamp}: {output}'
        )
    else:
        return screenshot_file


def _make_resize_cmd(image_file, dimensions, resized_file):
    # ffmpeg's "image2" image file muxer uses "%" for string formatting
    resized_file = resized_file.replace('%', '%%')
    return (
        _ffmpeg_executable(),
        '-y',
        '-loglevel', 'level+error',
        '-i', f'file:{image_file}',
        '-vf', f'scale={dimensions}',
        f'file:{resized_file}',
    )

def resize(image_file, width=None, height=None, target_file=None):
    """
    Resize image, preserve aspect ratio

    :param image_file: Path to source image
    :param width: Desired image width in pixels or `None`
    :param height: Desired image height in pixels or `None`
    :param target_file: Path to resized image or `None` to generate a path from
        `image_file`, `width` and `height`

    If `width` and `height` are falsy (the default) return `image_file` if
    `target_file` is falsy or copy `image_file` to `target_file` and return
    `target_file`.

    :raise ImageResizeError: if resizing fails

    :return: Path to resized image
    """
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
        extension = f'.width={width},height={height}.'
    elif width:
        dimensions = f'w={int(width)}:h=-1'
        extension = f'.width={width}.'
    elif height:
        dimensions = f'w=-1:h={int(height)}'
        extension = f'.height={height}.'
    else:
        if target_file:
            import shutil
            try:
                return str(shutil.copy2(image_file, target_file))
            except OSError as e:
                msg = e.strerror if e.strerror else str(e)
                raise errors.ImageResizeError(
                    f'Failed to copy {image_file} to {target_file}: {msg}'
                )
        else:
            return str(image_file)

    if not target_file:
        target_file = (
            utils.fs.strip_extension(image_file)
            + extension
            + utils.fs.file_extension(image_file)
        )
    _log.debug('Resizing to %r: %r', dimensions, image_file)
    _log.debug('Resize target: %r', target_file)

    cmd = _make_resize_cmd(image_file, dimensions, target_file)
    output = utils.subproc.run(cmd, ignore_errors=True, join_stderr=True)
    if not os.path.exists(target_file):
        raise errors.ImageResizeError(
            f'{image_file}: Failed to resize: {output}'
        )
    else:
        return str(target_file)
