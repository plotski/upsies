"""
Video metadata
"""

import collections
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
    _ffprobe_executable = 'ffprobe.exe'
else:
    _mediainfo_executable = 'mediainfo'
    _ffprobe_executable = 'ffprobe'


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
    mi = _run_mediainfo(first_video(path))
    parent_dir = os.path.dirname(path)
    if parent_dir:
        mi = mi.replace(parent_dir + os.sep, '')
    return mi


@functools.lru_cache(maxsize=None)
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
    try:
        return _duration_from_ffprobe(video_file_path)
    except (RuntimeError, errors.DependencyError, errors.ProcessError):
        return _duration_from_mediainfo(video_file_path)

def _duration_from_ffprobe(video_file_path):
    cmd = (
        _ffprobe_executable,
        '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        make_ffmpeg_input(video_file_path),
    )
    length = subproc.run(cmd, ignore_errors=True)
    try:
        return float(length.strip())
    except ValueError:
        raise RuntimeError(f'Unexpected output from {cmd}: {length!r}')

def _duration_from_mediainfo(video_file_path):
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


@functools.lru_cache(maxsize=None)
def width(path):
    """
    Return displayed width of video file `path` or `0`

    :param str path: Path to video file or directory. :func:`first_video` is
        applied.

    :return: int
    """
    try:
        video_track = default_track('video', path)
    except errors.ContentError:
        return 0
    else:
        return _get_display_width(video_track)

@functools.lru_cache(maxsize=None)
def height(path):
    """
    Return displayed height of video file `path` or `0`

    :param str path: Path to video file or directory. :func:`first_video` is
        applied.

    :return: int
    """
    try:
        video_track = default_track('video', path)
    except errors.ContentError:
        return 0
    else:
        return _get_display_height(video_track)

@functools.lru_cache(maxsize=None)
def resolution(path):
    """
    Return resolution of video file `path` (e.g. "1080p") or `None`

    :param str path: Path to video file or directory. :func:`first_video` is
        applied.
    """
    try:
        video_track = default_track('video', path)
    except errors.ContentError:
        return None

    # Expect non-wide (1392x1080), narrow (1920x800) and weird (1918x1040)
    std_resolution = _get_closest_standard_resolution(video_track)
    if std_resolution:
        # "p" or "i", default to "p"
        scan = video_track.get('ScanType', 'Progressive')[0].lower()
        _log.debug('Detected resolution: %s%s', std_resolution, scan)
        return f'{std_resolution}{scan}'

    return None

def _get_display_width(video_track):
    width = int(video_track.get('Width', 0))
    _log.debug('Stored width: %r', width)
    if width:
        # Actual aspect ratio may differ from display aspect ratio,
        # e.g. 960 x 534 is scaled up to 1280 x 534
        par = float(video_track.get('PixelAspectRatio') or 1.0)
        if par > 1.0:
            _log.debug('Display width: %r * %r = %r', width, par, width * par)
            width = width * par
    return int(width)

def _get_display_height(video_track):
    height = int(video_track.get('Height', 0))
    _log.debug('Stored height: %r', height)
    if height:
        # Actual aspect ratio may differ from display aspect ratio,
        # e.g. 960 x 534 is scaled up to 1280 x 534
        par = float(video_track.get('PixelAspectRatio') or 1.0)
        if par < 1.0:
            _log.debug('Display height: (1 / %r) * %r = %r', par, height, (1 / par) * height)
            height = (1 / par) * height
    return int(height)

_standard_resolutions = (
    # (width, height, standard resolution)
    # 4:3
    (640, 480, 480),
    (720, 540, 540),
    (768, 576, 576),
    (960, 720, 720),
    (1440, 1080, 1080),
    (2880, 2160, 2160),
    (5760, 4320, 4320),

    # 16:9
    (853, 480, 480),
    (960, 540, 540),
    (1024, 576, 576),
    (1280, 720, 720),
    (1920, 1080, 1080),
    (3840, 2160, 2160),
    (7680, 4320, 4320),

    # 21:9
    (853, 365, 480),
    (960, 411, 540),
    (1024, 438, 576),
    (1280, 548, 720),
    (1920, 822, 1080),
    (3840, 1645, 2160),
    (7680, 3291, 4320),
)

def _get_closest_standard_resolution(video_track):
    actual_width = _get_display_width(video_track)
    actual_height = _get_display_height(video_track)
    if actual_width and actual_height:
        # Find distances from actual display width/height to each standard
        # width/height. Categorize them by standard ratio.
        distances = collections.defaultdict(lambda: {})
        for std_width, std_height, std_resolution in _standard_resolutions:
            std_aspect_ratio = round(std_width / std_height, 1)
            w_dist = abs(std_width - actual_width)
            h_dist = abs(std_height - actual_height)
            resolution = (std_width, std_height, std_resolution)
            distances[std_aspect_ratio][w_dist] = distances[std_aspect_ratio][h_dist] = resolution

        # Find standard aspect ratio closest to the given aspect ratio
        actual_aspect_ratio = round(actual_width / actual_height, 1)
        _log.debug('Actual resolution: %4d x %4d: aspect ratio: %r',
                   actual_width, actual_height, actual_aspect_ratio)
        std_aspect_ratios = tuple(distances)
        closest_std_aspect_ratio = closest_number(actual_aspect_ratio, std_aspect_ratios)
        _log.debug('Closest standard aspect ratio: %r', closest_std_aspect_ratio)

        # Pick the standard resolution with the lowest distance to the given resolution
        dists = distances[closest_std_aspect_ratio]
        std_width, std_height, std_resolution = sorted(dists.items())[0][1]
    else:
        std_width, std_height, std_resolution = 0, 0, None

    _log.debug('Closest standard resolution: %r x %r -> %r x %r -> %r',
               actual_width, actual_height, std_width, std_height, std_resolution)
    return std_resolution


@functools.lru_cache(maxsize=None)
def frame_rate(path):
    """
    Return frames per second as :class:`float` of default video track or `0` if
    it can't be determined
    """
    try:
        video_track = default_track('video', path)
    except errors.ContentError:
        return 0
    else:
        return float(video_track.get('FrameRate', 0))


@functools.lru_cache(maxsize=None)
def bit_depth(path):
    """Return bit depth of default video track or `None` if it can't be determined"""
    try:
        video_track = default_track('video', path)
    except errors.ContentError:
        return None
    else:
        return video_track.get('BitDepth', None)


@functools.lru_cache(maxsize=None)
def is_hdr10(path):
    """
    Return `True` if `path` is HDR10 video, `False` otherwise, `None` if it
    can't be determined
    """
    try:
        video_track = default_track('video', path)
    except errors.ContentError:
        return None
    else:
        if 'BT.2020' in video_track.get('colour_primaries', ''):
            return True
        else:
            return False


@functools.lru_cache(maxsize=None)
def has_dual_audio(path):
    """
    Return `True` if `path` contains multiple audio tracks with different
    languages and one of them is English, `False` otherwise, `None` if it can't
    be determined
    """
    try:
        audio_tracks = tracks(path).get('Audio', ())
    except errors.ContentError:
        return None
    else:
        languages = set()
        for track in audio_tracks:
            if 'commentary' not in track.get('Title', '').lower():
                language = track.get('Language', '')
                if language:
                    languages.add(language.casefold())
        if len(languages) > 1 and 'en' in languages:
            return True
        else:
            return False


_audio_format_translations = (
    # (<format>, <<key>:<regex> dictionary>)
    # - All <regex>s must match each <key> to identify <format>.
    # - All identified <format>s are appended (e.g. "TrueHD Atmos").
    # - {<key>: None} means <key> must not exist.
    ('AAC', {'Format': re.compile(r'^AAC$')}),
    ('AC-3', {'Format': re.compile(r'^AC-3$')}),
    ('E-AC-3', {'Format': re.compile(r'^E-AC-3$')}),
    ('TrueHD', {'Format': re.compile(r'MLP ?FBA')}),
    ('TrueHD', {'Format_Commercial_IfAny': re.compile(r'TrueHD')}),
    ('Atmos', {'Format_Commercial_IfAny': re.compile(r'Atmos')}),
    ('DTS', {'Format': re.compile(r'^DTS$'), 'Format_Commercial_IfAny': None}),
    ('DTS-ES', {'Format_Commercial_IfAny': re.compile(r'DTS-ES')}),
    ('DTS-HD', {'Format_Commercial_IfAny': re.compile(r'DTS-HD(?! Master Audio)')}),
    ('DTS-HD MA', {'Format_Commercial_IfAny': re.compile(r'DTS-HD Master Audio'), 'Format_AdditionalFeatures': re.compile(r'XLL$')}),
    ('DTS:X', {'Format_AdditionalFeatures': re.compile(r'XLL X')}),
    ('FLAC', {'Format': re.compile(r'FLAC')}),
    ('MP3', {'Format': re.compile(r'MPEG Audio')}),
    ('Vorbis', {'Format': re.compile(r'\bVorbis\b')}),
    ('Vorbis', {'Format': re.compile(r'\bOgg\b')}),
)

@functools.lru_cache(maxsize=None)
def audio_format(path):
    """
    Return audio format (e.g. "AAC", "MP3") or `None`

    :param str path: Path to video file or directory. :func:`first_video` is
        applied.
    """
    try:
        audio_track = default_track('audio', path)
    except errors.ContentError:
        return None
    else:
        def is_match(regexs, audio_track):
            for key,regex in regexs.items():
                if regex is None:
                    if key in audio_track:
                        # `key` must not exists but it does
                        return False
                else:
                    # regex is not None
                    if key not in audio_track:
                        # `key` doesn't exist
                        return False
                    elif not regex.search(audio_track.get(key, '')):
                        # `key` has value that doesn't match `regex`
                        return False
            # All `regexs` match and no forbidden keys exist in `audio_track`
            return True

        _log.debug('Audio track for %r: %r', path, audio_track)
        parts = []
        for fmt,regexs in _audio_format_translations:
            if fmt not in parts and is_match(regexs, audio_track):
                parts.append(fmt)

        return ' '.join(parts) or None


# NOTE: guessit only recognizes 7.1, 5.1, 2.0 and 1.0
_audio_channels_translations = (
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
)

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
            for achan,regex in _audio_channels_translations:
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
        # _log.debug('Video track for %r: %r', path, video_track)
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

        # Find S\d+E01 in files to get the most common case without getting at
        # video durations
        first_video_regex = re.compile(r'(?:^|[ \.])S\d+E0*1[ \.]')
        for file in files:
            if first_video_regex.search(os.path.basename(file)):
                _log.debug('Found first episode: %r', file)
                return file

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
