import functools
import os
import re

from ..tools import mediainfo
from ..utils import LazyModule, fs

import logging  # isort:skip
_log = logging.getLogger(__name__)

# Disable debugging messages from rebulk
logging.getLogger('rebulk').setLevel(logging.WARNING)

_guessit = LazyModule(module='guessit', name='_guessit', namespace=globals())


def _file_and_parent(path):
    """Yield `basename` and `dirname` of `path`"""
    basename = fs.basename(path)
    dirname = os.path.dirname(path)
    yield basename
    if dirname and dirname != basename:
        yield dirname


@functools.lru_cache(maxsize=None)
def guessit(path):
    """
    Ameliorate guessit

    - Return regular `dict`.
    - The ``alternative_title`` is replaced by ``aka`` and its value comes from
      splitting the title at "AKA".
    - ``type`` is "season" if ``season`` is known but ``episode`` isn't.
    - ``year``, ``season`` and ``episode`` are `str`, not `int`.
    - ``source`` is "WEB-DL" or "WEBRip", not just "Web".
    - ``source`` is "Web" is uppercased to "WEB"
    - ``source`` is "DVDRip", "DVD9" and "DVD5", not just "DVD"
    - ``source`` includes "Hybrid" and "Remux" if applicable.
    - ``audio_codec`` is never a list.
    - ``audio_codec`` is abbreviated (e.g. "DD+" instead of "Dolby Digital Plus").
    - ``streaming_service`` value is abbreviated (e.g. "NF" instead of "Netflix").
    - Any streaming service is guessed by looking for all-caps string in front
      of "WEB-DL"/"WEBRip".
    - ``other`` is always a list.
    - ``edition`` is always a list.
    """
    guess = dict(_guessit.guessit(path))
    _log.debug('Original guess: %r', guess)

    _correct_alternative_title(guess)
    _enforce_list_fields(guess, 'other')
    _enforce_list_fields(guess, 'edition')
    _enforce_str(guess, 'year', 'season', 'episode')
    _add_season_type(guess)
    _detect_webdl_and_webrip(guess, path)
    _normalize_source(guess, path)
    _detect_any_streaming_service(guess, path)
    _abbreviate_streaming_service(guess, path)
    _detect_dvd_rip(guess)
    _detect_dvd_image(guess, path)
    _abbreviate_audio_codec(guess)
    _differentiate_between_h26n_and_x26n(guess, path)

    _log.debug('Improved guess: %r', guess)
    return guess


_title_aka_regex = re.compile(r' +AKA +')

def _correct_alternative_title(guess):
    # Guess it splits AKA at " - ", we want to split at " AKA "
    _enforce_list_fields(guess, 'alternative_title')
    if 'title' in guess:
        title_parts = [guess['title']]
        title_parts.extend(guess.get('alternative_title', ()))
        title = ' - '.join(title_parts)
        title_parts = _title_aka_regex.split(title, maxsplit=1)
        if len(title_parts) > 1:
            guess['title'], guess['aka'] = title_parts
        else:
            guess['title'] = title_parts[0]


def _enforce_list_fields(guess, key):
    # Fields that can be a list must always be a list
    if key in guess:
        if isinstance(guess[key], str):
            guess[key] = [guess[key]]
        elif guess[key] is None:
            guess[key] = []


def _enforce_str(guess, *keys):
    # For lists, make all items strings
    for key in keys:
        if key in guess and not isinstance(guess[key], str):
            if isinstance(guess[key], list):
                guess[key] = [str(v) for v in guess[key]]
            else:
                guess[key] = str(guess[key])


def _add_season_type(guess):
    # If "season" exists and "episode" does not, set "type" to "season"
    if guess.get('type') == 'episode' and 'episode' not in guess:
        guess['type'] = 'season'


_web_source_regex = re.compile(r'[ \.](WEB-?(?:DL|Rip))(?:[ \.]|$)', flags=re.IGNORECASE)

def _detect_webdl_and_webrip(guess, path):
    # Distinguish between WEB-DL and WEBRip
    if guess.get('source') == 'Web':
        # Look in file name and parent directory name first
        for name in _file_and_parent(path):
            match = _web_source_regex.search(name)
            if match:
                guess['source'] = match.group(1)
                return


_source_translation = {
    re.compile(r'(?i:Blu-?ray)') : 'BluRay',
    re.compile(r'(?i:WEB-?DL)')  : 'WEB-DL',
    re.compile(r'(?i:WEB-?Rip)') : 'WEBRip',
    re.compile(r'(?i:Web)')      : 'WEB',
}

_hybrid_regex = re.compile(r'(?i:hybrid[\. ]+blu-?ray|blu-?ray[\. ]+hybrid)')

def _normalize_source(guess, path):
    source = guess.get('source', None)
    if source is not None:
        for regex,source_fixed in _source_translation.items():
            if regex.search(source):
                guess['source'] = source_fixed
                break

        if guess['source'].lower() == 'web':
            # Guess WEBRip and WEB-DL based on encoder
            video_format = mediainfo.video_format(path)
            if video_format in ('x264', 'x265'):
                guess['source'] = 'WEBRip'
            elif video_format in ('H.264', 'H.265'):
                guess['source'] = 'WEB-DL'

        # guessit doesn't detect "Hybrid"
        for name in _file_and_parent(path):
            if _hybrid_regex.search(name):
                guess['source'] = 'Hybrid ' + guess['source']
                break

        if 'Remux' in guess.get('other', ()):
            guess['source'] += ' Remux'


_streaming_service_translation = {
    re.compile(r'(?i:Amazon)')               : 'AMZN',
    re.compile(r'(?i:Adult Swim)')           : 'AS',
    re.compile(r'(?i:Apple)')                : 'APTV',
    re.compile(r'(?i:BBC)')                  : 'BBC',
    re.compile(r'(?i:Cartoon Network)')      : 'CN',
    re.compile(r'(?i:Comedy Central)')       : 'CC',
    re.compile(r'(?i:DC Universe)')          : 'DCU',
    re.compile(r'(?i:Disney)')               : 'DSNP',
    re.compile(r'(?i:DNSP)')                 : 'DSNP',
    re.compile(r'(?i:HBO)')                  : 'HBO',
    re.compile(r'(?i:Hulu)')                 : 'HULU',
    re.compile(r'(?i:iTunes)')               : 'IT',
    re.compile(r'(?i:Netflix)')              : 'NF',
    re.compile(r'(?i:Nickelodeon)')          : 'NICK',
    re.compile(r'(?i:Playstation Network)')  : 'PSN',
    re.compile(r'(?i:Vudu)')                 : 'VUDU',
    re.compile(r'(?i:YouTube Red)')          : 'RED',
}

def _abbreviate_streaming_service(guess, path):
    if 'streaming_service' in guess:
        streaming_service = guess['streaming_service']
        for regex,abbrev in _streaming_service_translation.items():
            if regex.search(streaming_service):
                guess['streaming_service'] = abbrev
                return


_streaming_service_regex = re.compile(r'[ \.]([A-Z]+)[ \.](?i:WEB-?(?:DL|Rip))(?:[ \.]|$)')

def _detect_any_streaming_service(guess, path):
    if 'streaming_service' not in guess:
        for name in _file_and_parent(path):
            match = _streaming_service_regex.search(name)
            if match:
                guess['streaming_service'] = match.group(1)
                return


def _detect_dvd_rip(guess):
    if guess.get('source') == 'DVD' and 'Rip' in guess.get('other', ()):
        guess['source'] = 'DVDRip'


def _detect_dvd_image(guess, path):
    for name in _file_and_parent(path):
        if 'DVD9' in name:
            guess['source'] = 'DVD9'
            return
        if 'DVD5' in name:
            guess['source'] = 'DVD5'
            return


_audio_codec_translation = {
    re.compile(r'Dolby Digital Plus') : 'DD+',
    re.compile(r'Dolby Digital$')     : 'DD',
    re.compile(r'TrueHD')             : 'TrueHD',
    re.compile(r'Dolby Atmos')        : 'Atmos',
    re.compile(r'Master Audio')       : 'MA',
    re.compile(r'High Resolution')    : 'HR',
    re.compile(r'Extended Surround')  : 'ES',
    re.compile(r'High Efficiency')    : 'HE',
    re.compile(r'Low Complexity')     : 'LC',
    re.compile(r'High Quality')       : 'HQ',
}

def _abbreviate_audio_codec(guess):
    if 'audio_codec' in guess:
        if isinstance(guess['audio_codec'], str):
            infos = (guess['audio_codec'],)
        else:
            infos = guess['audio_codec']

        parts = []
        for info in infos:
            for regex,abbrev in _audio_codec_translation.items():
                if regex.search(info):
                    parts.append(abbrev)
                    continue

        if parts:
            guess['audio_codec'] = ' '.join(parts)
            guess['audio_codec'] = guess['audio_codec'].replace('DD TrueHD', 'TrueHD')
        else:
            # Codecs like "MP3" or "FLAC" are already abbreviated
            guess['audio_codec'] = ' '.join(infos)


_x264_regex = re.compile(r'(?i:[\. ]+x264[\. -])')
_x265_regex = re.compile(r'(?i:[\. ]+x265[\. -])')

def _differentiate_between_h26n_and_x26n(guess, path):
    if guess.get('video_codec') == 'H.264':
        for name in _file_and_parent(path):
            if _x264_regex.search(name):
                guess['video_codec'] = 'x264'
                break
    if guess.get('video_codec') == 'H.265':
        for name in _file_and_parent(path):
            if _x265_regex.search(name):
                guess['video_codec'] = 'x265'
                break
