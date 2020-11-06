import functools
import os
import shlex

from .. import binaries, errors
from . import LazyModule, fs, subproc

import logging  # isort:skip
_log = logging.getLogger(__name__)

natsort = LazyModule(module='natsort', namespace=globals())


_video_file_extensions = ('mkv', 'mp4', 'ts', 'avi', 'vob')

def first_video(path):
    """
    Find first video file (e.g. first episode from season)

    Directories are walked recursively and contents are sorted naturally, e.g. "File
    2.mkv" is sorted before "File 10.mkv". Video files are detected by file extension.

    :param str path: Path to file or directory

    :raise ContentError: if no video file can be found or if it is unreadable

    :return: Path to first video file if `path` is a directory, `path` itself otherwise
    :rtype: str
    """
    if os.path.isdir(path):
        if os.path.isdir(os.path.join(path, 'BDMV')):
            # Blu-ray copy
            return str(path)

        for root, dirnames, filenames in os.walk(path):
            # Check all files in this directory
            for filename in natsort.natsorted(filenames, key=str.casefold):
                if fs.file_extension(filename).lower() in _video_file_extensions:
                    return os.path.join(root, filename)

            # No video files were found, dive into subdirectories
            for dirname in natsort.natsorted(dirnames, key=str.casefold):
                return first_video(os.path.join(path, dirname))

        raise errors.ContentError(f'{path}: No video file found')
    else:
        fs.assert_file_readable(path)
        if fs.file_extension(path) in _video_file_extensions:
            return str(path)
        else:
            raise errors.ContentError(f'{path}: Not a video file')


@functools.lru_cache(maxsize=None)
def length(filepath):
    """
    Return video length in seconds (float)

    :raise ContentError: if `filepath` is not readable
    """
    fs.assert_file_readable(filepath)
    cmd = (
        binaries.ffprobe,
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        make_ffmpeg_input(filepath),
    )

    # Catch DependencyError because we want a nice error message if ffprobe is
    # not installed. Do not catch ProcessError because things like wrong ffprobe
    # arguments are bugs.
    try:
        length = subproc.run(cmd, ignore_errors=True)
    except errors.DependencyError as e:
        raise errors.ContentError(e)

    try:
        return float(length)
    except ValueError:
        raise RuntimeError(f'Unexpected output from command: '
                           f'{" ".join(shlex.quote(str(arg)) for arg in cmd)}:\n'
                           f'{length}')


def make_ffmpeg_input(path):
    """
    Make `path` palatable for ffmpeg

    - If path is a directory and contains a subdirectory named "BDMV", "bluray:"
      is prepended to `path`.

    - If path is a directory and contains a subdirectory named "VIDEO_TS", the
      longest .VOB file (in seconds) is returned. (ffmpeg does not support DVD
      directory structures.)

    - By default, `path` is returned unchanged.

    :param str path: Path to file or directory
    """
    try:
        # Detect Blu-ray
        if os.path.exists(os.path.join(path, 'BDMV')):
            return f'bluray:{path}'

        # Detect DVD
        if os.path.exists(os.path.join(path, 'VIDEO_TS')):
            # FFmpeg doesn't seem to support reading DVD.  We work around this
            # by finding the longest .VOB file (in seconds) in the VIDEO_TS
            # directory and use that as input.
            video_ts = os.path.join(path, 'VIDEO_TS')
            vobs = sorted(os.path.join(video_ts, f)
                          for f in os.listdir(video_ts)
                          if f.upper().endswith('VOB'))
            _log.debug('All VOBs: %r', vobs)
            longest_vob = sorted(vobs, key=length, reverse=True)[0]
            _log.debug('Longest VOB: %r', longest_vob)
            return longest_vob

    except OSError:
        pass

    return str(path)
