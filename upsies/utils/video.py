"""
Video metadata
"""

import functools
import json
import os
import re

from .. import constants, errors
from . import closest_number, fs, os_family, subproc

import logging  # isort:skip
_log = logging.getLogger(__name__)


if os_family() == 'windows':
    _mediainfo_executable = 'mediainfo.exe'
else:
    _mediainfo_executable = 'mediainfo'


def _run_mediainfo(video_file_path, *args):
    fs.assert_file_readable(video_file_path)
    cmd = (_mediainfo_executable, video_file_path) + args

    # Translate DependencyError to ContentError so callers have to expect less
    # exceptions. Do not catch ProcessError because things like wrong mediainfo
    # arguments are bugs.
    try:
        return subproc.run(cmd, cache=True)
    except errors.DependencyError as e:
        raise errors.ContentError(e)


def mediainfo(path):
    """
    ``mediainfo`` output as a string

    The parent directory of `path` is redacted.

    :param str path: Path to video file or directory. :func:`first_video` is
        applied.

    :raise ContentError: if anything goes wrong

    :return: Output from ``mediainfo``
    :rtype: str
    """
    text = _run_mediainfo(first_video(path))
    parent_dir = os.path.dirname(path)
    return text.replace(parent_dir + os.sep, '')


def duration(path):
    """
    Return video duration in seconds (float)

    :param str path: Path to video file or directory. :func:`first_video` is
        applied.

    Return ``0.0`` if video duration can't be determined.

    :raise ContentError: if anything goes wrong
    """
    return _duration(first_video(path))

def _duration(video_file_path):
    tracks = _tracks(video_file_path)
    try:
        return float(tracks.get('General')[0]['Duration'])
    except (KeyError, IndexError, TypeError, ValueError):
        return 0.0


def tracks(path):
    """
    ``mediainfo --Output=JSON`` as dictionary that maps each track's ``@type``
    to a list of the tracks

    :param str path: Path to video file or directory. :func:`first_video` is
        applied.

    :raise ContentError: if anything goes wrong
    """
    return _tracks(first_video(path))

def _tracks(video_file_path):
    stdout = _run_mediainfo(video_file_path, '--Output=JSON')
    tracks = {}
    try:
        for track in json.loads(stdout)['media']['track']:
            if not track['@type'] in tracks:
                tracks[track['@type']] = []
            tracks[track['@type']].append(track)
        return tracks
    except (ValueError, TypeError) as e:
        raise RuntimeError(f'{video_file_path}: Unexpected mediainfo output: {stdout}: {e}')
    except KeyError as e:
        raise RuntimeError(f'{video_file_path}: Unexpected mediainfo output: {stdout}: Missing field: {e}')


def default_track(type, path):
    """
    Find default track

    :param str type: "video" or "audio"
    :param str path: Path to video file or directory. :func:`first_video` is
        applied.

    :raise ContentError: if anything goes wrong

    :return: Default track of `type` or empty `dict`
    :rtype: dict
    """
    all_tracks = tracks(path)

    # Find track marked as default
    try:
        for track in all_tracks[type.capitalize()]:
            if track.get('Default') == 'Yes':
                return track
    except KeyError:
        pass

    # Default to first track
    try:
        return all_tracks[type.capitalize()][0]
    except (KeyError, IndexError):
        pass

    raise errors.ContentError(f'{path}: No {type.lower()} track found')


_standard_widths = (640, 768, 1280, 1920, 3840, 7680)
_standard_heights = (480, 576, 720, 1080, 2160, 4320)

@functools.lru_cache(maxsize=None)
def resolution(path):
    """
    Return resolution of video file `path` (e.g. "1080p") or `None`

    :param str path: Path to video file or directory. :func:`first_video` is
        applied.
    """
    # Expect non-wide (1392x1080), narrow (1920x800) and weird (1918x1040)
    try:
        video_track = default_track('video', path)
    except errors.ContentError:
        return None

    height = int(video_track.get('Height', 0))
    width = int(video_track.get('Width', 0))
    if height and width:
        # Actual aspect ratio may differ from display aspect ratio,
        # e.g.  960 x 534 is scaled up to 1280 x 534
        dar = float(video_track.get('PixelAspectRatio', 0))
        if dar:
            height = height * dar

        # Find closest height and width in standard resolutions
        std_height = closest_number(height, _standard_heights)
        std_width = closest_number(width, _standard_widths)

        # The resolution with the highest index wins
        index = max(_standard_heights.index(std_height),
                    _standard_widths.index(std_width))
        res = _standard_heights[index]

        # "p" or "i", default to "p"
        scan = video_track.get('ScanType', 'Progressive')[0].lower()
        _log.debug('Detected resolution: %r x %r -> %s%s', width, height, res, scan)
        return f'{res}{scan}'

    return None


_audio_translations = {
    'formats': (
        ('AAC', {'Format': re.compile(r'AAC')}),
        ('DD', {'Format': re.compile(r'^AC-3')}),
        ('DD', {'Format_Commercial_IfAny': re.compile(r'Dolby Digital(?! Plus)')}),
        ('DD+', {'Format': re.compile(r'E-AC-3')}),
        ('DD+', {'Format_Commercial_IfAny': re.compile(r'Dolby Digital Plus')}),
        ('DTS:X', {'Format_AdditionalFeatures': re.compile(r'XLL X')}),
        ('DTS-ES', {'Format_Commercial_IfAny': re.compile(r'DTS-ES')}),
        ('DTS-HD MA', {'Format_Commercial_IfAny': re.compile(r'DTS-HD Master Audio')}),
        ('DTS-HD', {'Format_Commercial_IfAny': re.compile(r'DTS-HD(?! Master Audio)')}),
        ('DTS', {'Format': re.compile(r'DTS')}),
        ('FLAC', {'Format': re.compile(r'FLAC')}),
        ('MP3', {'Format': re.compile(r'MPEG Audio')}),
        ('TrueHD', {'Format': re.compile(r'MLP ?FBA')}),
        ('TrueHD', {'Format_Commercial_IfAny': re.compile(r'TrueHD')}),
        ('Vorbis', {'Format': re.compile(r'\bVorbis\b')}),
        ('Vorbis', {'Format': re.compile(r'\bOgg\b')}),
    ),
    'features': (
        ('Atmos', {'Format_Commercial_IfAny': re.compile(r'Dolby Atmos')}),
    ),
    # NOTE: guessit only recognizes 7.1, 5.1, 2.0 and 1.0
    'channels': (
        ('1.0', re.compile(r'^1$')),
        ('2.0', re.compile(r'^2$')),
        ('2.0', re.compile(r'^3$')),
        ('2.0', re.compile(r'^4$')),
        ('2.0', re.compile(r'^5$')),
        ('5.1', re.compile(r'^6$')),
        ('5.1', re.compile(r'^7$')),
        ('7.1', re.compile(r'^8$')),
        ('7.1', re.compile(r'^9$')),
        ('7.1', re.compile(r'^10$')),
    ),
}

@functools.lru_cache(maxsize=None)
def audio_format(path):
    """
    Return audio format (e.g. "DD", "MP3") or `None`

    :param str path: Path to video file or directory. :func:`first_video` is
        applied.
    """
    # Return audio format, e.g. "DTS"
    def translate_format(audio_track):
        for fmt,regexs in _audio_translations['formats']:
            for key,regex in regexs.items():
                value = audio_track.get(key)
                if value:
                    if regex.search(value):
                        return fmt
        return ''

    # Return list of features like "Atmos"
    def translate_features(audio_track):
        feats = []
        for feat,regexs in _audio_translations['features']:
            for key,regex in regexs.items():
                value = audio_track.get(key)
                if value:
                    if regex.search(value):
                        feats.append(feat)
        return feats

    try:
        audio_track = default_track('audio', path)
    except errors.ContentError:
        return None
    else:
        _log.debug('Audio track for %r: %r', path, audio_track)

        fmt = translate_format(audio_track)
        if fmt:
            audio_format = ' '.join([fmt] + translate_features(audio_track))
        else:
            audio_format = None
        _log.debug('Detected audio format: %s', audio_format)
        return audio_format


@functools.lru_cache(maxsize=None)
def audio_channels(path):
    """
    Return audio channels (e.g. "5.1") or `None`

    :param str path: Path to video file or directory. :func:`first_video` is
        applied.
    """
    try:
        audio_track = default_track('audio', path)
    except errors.ContentError:
        return None
    else:
        audio_channels = None
        channels = audio_track.get('Channels', '')
        if channels:
            for achan,regex in _audio_translations['channels']:
                if regex.search(channels):
                    audio_channels = achan
                    break
        _log.debug('Detected audio channels: %s', audio_channels)
        return audio_channels


_video_translations = (
    ('x264', {'Encoded_Library_Name': re.compile(r'^x264$')}),
    ('x265', {'Encoded_Library_Name': re.compile(r'^x265$')}),
    ('XviD', {'Encoded_Library_Name': re.compile(r'^XviD$')}),
    ('H.264', {'Format': re.compile(r'^AVC$')}),
    ('H.265', {'Format': re.compile(r'^HEVC$')}),
    ('VP9', {'Format': re.compile(r'^VP9$')}),
    ('MPEG-2', {'Format': re.compile(r'^MPEG Video$'), 'Format_Version': re.compile(r'^2$')}),
)

@functools.lru_cache(maxsize=None)
def video_format(path):
    """
    Return video format or x264/x265/XviD if they were used or `None`

    :param str path: Path to video file or directory. :func:`first_video` is
        applied.
    """
    def translate(video_track):
        for vfmt,regexs in _video_translations:
            for key,regex in regexs.items():
                value = video_track.get(key)
                if value:
                    if regex.search(value):
                        return vfmt
        return None

    try:
        video_track = default_track('video', path)
    except errors.ContentError:
        return None
    else:
        _log.debug('Video track for %r: %r', path, video_track)
        video_format = translate(video_track)
        _log.debug('Detected video format: %s', video_format)
        return video_format


@functools.lru_cache(maxsize=None)
def first_video(path):
    """
    Find first video file (e.g. first episode from season)

    Video files are detected by file extension.

    Directories are walked recursively and contents are sorted naturally,
    e.g. "2.mkv" is sorted before "10.mkv".

    Paths to Blu-ray images (directories that contain a "BDMV" directory) are
    simply returned.

    To avoid samples and similar files, `path` is filtered through
    :func:`filter_similar_duration`.

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
        files = fs.file_list(path, extensions=constants.VIDEO_FILE_EXTENSIONS)

    if not files:
        raise errors.ContentError(f'{path}: No video file found')
    else:
        # To avoid using samples or very short .VOBs, remove any videos that are
        # very short compared to the average duration.
        considered_files = filter_similar_duration(files)
        first_file = str(considered_files[0])
        return first_file


@functools.lru_cache(maxsize=None)
def filter_similar_duration(video_file_paths):
    """
    Filter `video_file_paths` for comparable video duration

    Exclude any videos that are shorter than 50% of the average.

    This is useful to exclude samples or short .VOBs from DVD images.

    .. note:: Because this function is decorated with
       :func:`functools.lru_cache`, `video_file_paths` should be a tuple (or any
       other hashable sequence).

    :params video_file_paths: Hashable sequence of video file paths

    :return: Tuple of video file paths

    :raise ContentError: if any path in `video_file_paths` is not readable
    """
    paths = tuple(video_file_paths)
    if len(paths) < 2:
        return paths
    else:
        durations = {fp: _duration(fp) for fp in video_file_paths}
        avg = sum(durations.values()) / len(durations)
        min_duration = avg * 0.5
        return tuple(fp for fp,l in durations.items()
                     if l >= min_duration)


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
    # Detect Blu-ray
    if os.path.exists(os.path.join(path, 'BDMV')):
        return f'bluray:{path}'

    # Detect DVD
    if os.path.exists(os.path.join(path, 'VIDEO_TS')):
        # FFmpeg doesn't seem to support reading DVD.  We work around this
        # by finding the first .VOB with a reasonable length.
        vobs = fs.file_list(os.path.join(path, 'VIDEO_TS'))
        _log.debug('All VOBs: %r', vobs)
        reasonable_vobs = filter_similar_duration(vobs)
        _log.debug('Reasonable VOBs: %r', reasonable_vobs)
        if reasonable_vobs:
            return reasonable_vobs[0]

    return str(path)
