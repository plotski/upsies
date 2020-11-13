import functools
import json
import os
import re

from .. import binaries, errors, utils

import logging  # isort:skip
_log = logging.getLogger(__name__)


def _run_mediainfo(path, *args):
    try:
        video_file_path = utils.video.first_video(path)
    except errors.ContentError as e:
        raise errors.MediainfoError(e)

    cmd = (binaries.mediainfo, video_file_path) + args

    # Catch DependencyError because we want a nice error message if mediainfo is
    # not installed. Do not catch ProcessError because things like wrong
    # mediainfo arguments are bugs.
    try:
        return utils.subproc.run(cmd, cache=True)
    except errors.DependencyError as e:
        raise errors.MediainfoError(e)


def as_string(path):
    """
    Regular ``mediainfo`` output

    The parent directory of `path` is removed from the returned string.

    :param str path: Path to video file

    :raise MediainfoError: if something goes wrong

    :return: Output from ``mediainfo``
    :rtype: str
    """
    return _run_mediainfo(path).replace(os.path.dirname(path) + os.sep, '')


def tracks(path):
    """
    Get tracks from video file

    Run ``mediainfo --Output=JSON path/to/video.mkv`` to find available fields.

    :param str path: Path to video file

    :raise MediainfoError: if something goes wrong

    :return: Media tracks
    :rtype: list of dicts
    """
    stdout = _run_mediainfo(path, '--Output=JSON')
    if stdout.strip():
        try:
            return json.loads(stdout)['media']['track']
        except (ValueError, TypeError) as e:
            raise RuntimeError(f'{path}: Unexpected mediainfo output: {stdout}: {e}')
        except KeyError as e:
            raise RuntimeError(f'{path}: Unexpected mediainfo output: {stdout}: Missing field: {e}')
    else:
        return []


def default_track(type, path):
    """
    Find default track

    :param str type: "video" or "audio"
    :param str path: Path to video file

    :return: Default track of `type`
    :rtype: dict
    """
    try:
        all_tracks = tracks(path)
    except errors.MediainfoError as e:
        _log.debug('Error from mediainfo: %r', e)
    else:
        # Find track marked as default
        for track in all_tracks:
            if track.get('@type') == type.capitalize() and track.get('Default') == 'Yes':
                return track
        # Default to first track
        for track in all_tracks:
            if track.get('@type') == type.capitalize():
                return track
    return {}


_standard_widths = (640, 768, 1280, 1920, 3840, 7680)
_standard_heights = (480, 576, 720, 1080, 2160, 4320)

@functools.lru_cache(maxsize=None)
def resolution(path):
    """Return resolution of video file `path` (e.g. 1080p) or None"""
    # Expect non-wide (1392x1080), narrow (1920x800) and weird (1918x1040)
    video_track = default_track('video', path)
    height = int(video_track.get('Height', 0))
    width = int(video_track.get('Width', 0))
    if height and width:
        # Find closest height and width in standard resolutions
        std_height = utils.closest_number(height, _standard_heights)
        std_width = utils.closest_number(width, _standard_widths)

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
        ('DTS:X', {'Format_AdditionalFeatures': re.compile(r'XLL X')}),
        ('DTS-HD', {'Format_Commercial_IfAny': re.compile(r'DTS-HD(?! Master Audio)')}),
        ('DTS-ES', {'Format_Commercial_IfAny': re.compile(r'DTS-ES')}),
        ('DTS-HD MA', {'Format_Commercial_IfAny': re.compile(r'DTS-HD Master Audio')}),
        ('DD', {'Format_Commercial_IfAny': re.compile(r'Dolby Digital(?! Plus)')}),
        ('DD+', {'Format_Commercial_IfAny': re.compile(r'Dolby Digital Plus')}),
        ('TrueHD', {'Format_Commercial_IfAny': re.compile(r'TrueHD')}),
        ('AAC', {'Format': re.compile(r'AAC')}),
        ('DD', {'Format': re.compile(r'^AC-3')}),
        ('DD+', {'Format': re.compile(r'E-AC-3')}),
        ('DTS', {'Format': re.compile(r'DTS')}),
        ('TrueHD', {'Format': re.compile(r'MLP ?FBA')}),
        ('FLAC', {'Format': re.compile(r'FLAC')}),
        ('MP3', {'Format': re.compile(r'MPEG Audio')}),
    ),
    'features': (
        ('Atmos', {'Format_Commercial_IfAny': re.compile(r'Dolby Atmos')}),
    ),
    'channels': (
        ('1.0', re.compile(r'^1$')),
        ('2.0', re.compile(r'^2$')),
        ('2.1', re.compile(r'^3$')),
        ('3.1', re.compile(r'^4$')),
        ('4.1', re.compile(r'^5$')),
        ('5.1', re.compile(r'^6$')),
        ('6.1', re.compile(r'^7$')),
        ('7.1', re.compile(r'^8$')),
    ),
}

@functools.lru_cache(maxsize=None)
def audio_format(path):
    """Return audio format (e.g. "DTS:X", "TrueHD Atmos") or None"""
    # Return audio format, e.g. "DTS"
    def format(audio_track):
        for fmt,regexs in _audio_translations['formats']:
            for key,regex in regexs.items():
                value = audio_track.get(key)
                if value:
                    if regex.search(value):
                        return fmt
        return ''

    # Return list of features like "Atmos"
    def features(audio_track):
        feats = []
        for feat,regexs in _audio_translations['features']:
            for key,regex in regexs.items():
                value = audio_track.get(key)
                if value:
                    if regex.search(value):
                        feats.append(feat)
        return feats

    audio_format = None
    audio_track = default_track('audio', path)
    _log.debug('Audio track for %r: %r', path, audio_track)

    fmt = format(audio_track)
    if fmt:
        audio_format = ' '.join([fmt] + features(audio_track))
    _log.debug('Detected audio format: %s', audio_format)
    return audio_format


@functools.lru_cache(maxsize=None)
def audio_channels(path):
    """Return audio channels (e.g. "5.1") or None"""
    audio_track = default_track('audio', path)
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
    """Return video format or x264/x265/XviD if they were used or None"""
    def format(video_track):
        for vfmt,regexs in _video_translations:
            for key,regex in regexs.items():
                value = video_track.get(key)
                if value:
                    if regex.search(value):
                        return vfmt
        return None

    video_track = default_track('video', path)
    _log.debug('Video track for %r: %r', path, video_track)
    video_format = format(video_track)
    _log.debug('Detected video format: %s', video_format)
    return video_format
