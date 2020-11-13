import functools
import os
import shlex

from .. import binaries, errors
from . import LazyModule, fs, subproc

import logging  # isort:skip
_log = logging.getLogger(__name__)

natsort = LazyModule(module='natsort', namespace=globals())


_video_file_extensions = ('mkv', 'mp4', 'ts', 'avi')

@functools.lru_cache(maxsize=None)
def first_video(path):
    """
    Find first video file (e.g. first episode from season)

    Video files are detected by file extension.

    Directories are walked recursively and contents are sorted naturally,
    e.g. "2.mkv" is sorted before "10.mkv".

    Paths to Blu-ray images (directories that contain a "BDMV" directory) are
    simply returned.

    For paths to DVD images (directories that contain a "VIDEO_TS" directory),
    the first .VOB file with a reasonable length is returned.

    :param str path: Path to file or directory

    :return: path to video file
    :rtype: str

    :raise ContentError: if no video file can be found or if it is unreadable
    """
    if os.path.isdir(path) and os.path.isdir(os.path.join(path, 'BDMV')):
        # Blu-ray image; ffmpeg can read that with the "bluray:" protocol
        return str(path)
    elif os.path.isdir(path) and os.path.isdir(os.path.join(path, 'VIDEO_TS')):
        # DVD image; ffmpeg can't read that so we get a list of .VOBs
        files = fs.file_list(path, extensions=('VOB',))
    else:
        files = fs.file_list(path, extensions=_video_file_extensions)

    if not files:
        raise errors.ContentError(f'{path}: No video file found')
    else:
        # To avoid using samples or very short .VOBs, remove any videos that are
        # very short compared to the average length.
        considered_files = filter_similar_length(files)
        first_file = str(considered_files[0])
        fs.assert_file_readable(first_file)
        return first_file


@functools.lru_cache(maxsize=None)
def filter_similar_length(filepaths):
    """
    Filter `filepaths` for comparable video duration

    Exclude any videos that are shorter than 50% of the average video length.

    This is useful to exclude samples or short .VOBs from DVD images.

    .. note:: Because this function is wrapped in `functools.lru_cache`,
        `filepaths` should be a tuple (or any other hashable sequence).

    :params filepaths: Hashable sequence of video file paths

    :return: Tuple of video file paths

    :raise ContentError: if any path in `filepaths` is not readable
    """
    lengths = {fp: length(fp) for fp in filepaths}
    avg = sum(lengths.values()) / len(lengths)
    min_length = avg * 0.5
    return tuple(fp for fp,l in lengths.items()
                 if l >= min_length)


@functools.lru_cache(maxsize=None)
def length(filepath):
    """
    Return video length in seconds (float)

    Return `0.0` if video length can't be determined.

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

    if length.strip().casefold() == 'n/a':
        return 0.0

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
