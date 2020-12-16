"""
`guessit <https://guessit.io/>`_ abstraction layer
"""

import collections
import os
import re

from . import LazyModule, ReleaseType, cache, fs, mediainfo

import logging  # isort:skip
_log = logging.getLogger(__name__)

# Disable debugging messages from rebulk
logging.getLogger('rebulk').setLevel(logging.WARNING)

_guessit = LazyModule(module='guessit', name='_guessit', namespace=globals())


class ReleaseInfo(collections.abc.MutableMapping):
    """
    Get information from release name

    .. note::

       Consider using :class:`~.release_name.ReleaseName` instead to get values
       from analyzing file contents and better validation when setting values.

    :param str path: Release name or path to release

    This is a simple dictionary with the following keys:

      - ``type`` (:class:`~.utils.ReleaseType` enum)
      - ``title``
      - ``aka`` (Also Known As; anything after "AKA" in the title)
      - ``year``
      - ``season``
      - ``episode`` (may be a :class:`list` for multi-episodes,
        e.g. "S01E01E02")
      - ``episode_title``
      - ``edition`` (:class:`list` of "Extended", "Uncut", etc)
      - ``resolution``
      - ``service`` (Streaming service abbreviation)
      - ``source`` ("BluRay", "WEB-DL", etc)
      - ``audio_codec`` (Audio codec abbreviation)
      - ``audio_channels`` (e.g. 2.0 or 7.1)
      - ``video_codec``
      - ``group``

    Unless documented otherwise above, all values are strings. Unknown values
    are empty strings.
    """

    def __init__(self, path):
        self._path = path
        self._dict = {}

    @cache.property
    def _guessit(self):
        path = self._path
        # guessit doesn't detect AC3 if it's called "AC-3"
        path = re.sub(r'([ \.])(?i:AC-?3)([ \.])', r'\1AC3\2', path)
        path = re.sub(r'([ \.])(?i:E-?AC-?3)([ \.])', r'\1EAC3\2', path)
        guess = dict(_guessit.guessit(path))
        _log.debug('Original guess: %r', guess)
        return guess

    def __contains__(self, name):
        return hasattr(self, f'_get_{name}')

    def __getitem__(self, name):
        if name not in self:
            raise KeyError(name)
        else:
            value = self._dict.get(name, None)
            if value is None:
                value = self[name] = getattr(self, f'_get_{name}')()
            return value

    def __setitem__(self, name, value):
        if not hasattr(self, f'_get_{name}'):
            raise KeyError(name)
        else:
            self._dict[name] = value

    def __delitem__(self, name):
        if not hasattr(self, f'_get_{name}'):
            raise KeyError(name)
        elif name in self._dict:
            del self._dict[name]

    def __iter__(self):
        return iter(name[5:] for name in dir(type(self))
                    if name.startswith('_get_'))

    def __len__(self):
        return len(tuple(name[5:] for name in dir(type(self))
                         if name.startswith('_get_')))

    def _get_type(self):
        type = self._guessit.get('type')
        if not type:
            return ReleaseType.unknown
        # Detect season type
        elif type == 'episode' and 'episode' not in self._guessit:
            return ReleaseType.season
        elif self._guessit['type'] == 'episode':
            return ReleaseType.episode
        else:
            return ReleaseType(self._guessit['type'])

    _title_aka_regex = re.compile(r' +AKA +')

    @cache.property
    def _title_parts(self):
        # Guess it splits AKA at " - ", we want to split at " AKA "
        title_parts = [self._guessit.get('title', '')]
        if self._guessit.get('alternative_title'):
            title_parts.extend(_as_list(self._guessit, 'alternative_title'))
        title = ' - '.join(title_parts)
        title_parts = self._title_aka_regex.split(title, maxsplit=1)
        if len(title_parts) > 1:
            return {'title': title_parts[0], 'aka': title_parts[1]}
        else:
            return {'title': title_parts[0], 'aka': ''}

    def _get_title(self):
        return self._title_parts['title']

    def _get_aka(self):
        return self._title_parts['aka']

    def _get_year(self):
        return _as_str(self._guessit, 'year')

    def _get_season(self):
        return _as_str(self._guessit, 'season')

    def _get_episode(self):
        return _as_str_or_list_of_str(self._guessit, 'episode')

    def _get_episode_title(self):
        return str(self._guessit.get('episode_title', ''))

    def _get_edition(self):
        return _as_list(self._guessit, 'edition')

    def _get_resolution(self):
        return self._guessit.get('screen_size', '')

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
    _streaming_service_regex = re.compile(r'[ \.]([A-Z]+)[ \.](?i:WEB-?(?:DL|Rip))(?:[ \.]|$)')

    def _get_service(self):
        service = self._guessit.get('streaming_service', '')
        if not service:
            for name in _file_and_parent(self._path):
                match = self._streaming_service_regex.search(name)
                if match:
                    service = match.group(1)

        for regex,abbrev in self._streaming_service_translation.items():
            if regex.search(service):
                service = abbrev
                break

        return service

    _source_translation = {
        re.compile(r'(?i:blu-?ray)') : 'BluRay',
        re.compile(r'(?i:dvd-?rip)') : 'DVDRip',
        re.compile(r'(?i:web-?dl)')  : 'WEB-DL',
        re.compile(r'(?i:web-?rip)') : 'WEBRip',
        re.compile(r'(?i:web)')      : 'WEB',
    }
    _sources_regex = r'(?:' + '|'.join(r.pattern for r in _source_translation) + ')'
    _hybrid_regex = re.compile(rf'[\. ]+(?:hybrid[\. ]+{_sources_regex}'
                               r'|'
                               rf'{_sources_regex}[\. ]+hybrid)[\. ]+',
                               flags=re.IGNORECASE)
    _web_source_regex = re.compile(r'[ \.](WEB-?(?:DL|Rip))(?:[ \.]|$)', flags=re.IGNORECASE)

    def _get_source(self):
        source = self._guessit.get('source', '')
        if source.lower() == 'web':
            # Distinguish between WEB-DL and WEBRip
            # Look in file name and parent directory name
            for name in _file_and_parent(self._path):
                match = self._web_source_regex.search(name)
                if match:
                    source = match.group(1)
                    break

            # Guess WEBRip and WEB-DL based on encoder
            if source.lower() == 'web':
                video_format = mediainfo.video_format(self._path)
                if video_format in ('x264', 'x265'):
                    source = 'WEBRip'
                elif video_format in ('H.264', 'H.265'):
                    source = 'WEB-DL'

        elif source == 'DVD':
            # Detect DVDRip
            if 'Rip' in self._guessit.get('other', ()):
                source = 'DVDRip'
            # Detect DVD images
            else:
                for name in _file_and_parent(self._path):
                    if 'DVD9' in name:
                        source = 'DVD9'
                        break
                    if 'DVD5' in name:
                        source = 'DVD5'
                        break

        if source:
            # Fix spelling
            for regex,source_fixed in self._source_translation.items():
                if regex.search(source):
                    source = source_fixed
                    break

        # guessit ignores "Hybrid"
        for name in _file_and_parent(self._path):
            if self._hybrid_regex.search(name):
                source = 'Hybrid ' + source
                break

        # Detect Remux
        if 'Remux' in self._guessit.get('other', ()):
            source += ' Remux'

        return source

    _audio_codec_translation = {
        re.compile(r'^AC-?3')             : 'DD',
        re.compile(r'Dolby Digital$')     : 'DD',
        re.compile(r'^E-?AC-?3')          : 'DD+',
        re.compile(r'Dolby Digital Plus') : 'DD+',
        re.compile(r'TrueHD')             : 'TrueHD',
        re.compile(r'Dolby Atmos')        : 'Atmos',
        re.compile(r'Master Audio')       : 'MA',
        re.compile(r'High Resolution')    : 'HR',
        re.compile(r'Extended Surround')  : 'ES',
        re.compile(r'High Efficiency')    : 'HE',
        re.compile(r'Low Complexity')     : 'LC',
        re.compile(r'High Quality')       : 'HQ',
    }

    def _get_audio_codec(self):
        audio_codec = self._guessit.get('audio_codec')
        if not audio_codec:
            return ''
        else:
            if isinstance(audio_codec, str):
                infos = [audio_codec]
            else:
                infos = audio_codec

            parts = []
            for info in infos:
                for regex,abbrev in self._audio_codec_translation.items():
                    if regex.search(info):
                        parts.append(abbrev)
                        continue

            if parts:
                audio_codec = ' '.join(parts)
                audio_codec = audio_codec.replace('DD TrueHD', 'TrueHD')
            else:
                # Codecs like "MP3" or "FLAC" are already abbreviated
                audio_codec = ' '.join(infos)

            return audio_codec

    # Look for channels after year or season
    _audio_channels_regex = re.compile(r'[ \.](?i:\d{4}|s\d{2,}).*?[ \.]+(\d\.\d)[ \.]')

    def _get_audio_channels(self):
        audio_channels = self._guessit.get('audio_channels', '')
        if not audio_channels:
            for name in _file_and_parent(self._path):
                match = self._audio_channels_regex.search(name)
                if match:
                    return match.group(1)
        return audio_channels

    _x264_regex = re.compile(r'(?i:[\. ]+x264[\. -])')
    _x265_regex = re.compile(r'(?i:[\. ]+x265[\. -])')

    def _get_video_codec(self):
        video_codec = self._guessit.get('video_codec', '')
        if video_codec == 'H.264':
            for name in _file_and_parent(self._path):
                if self._x264_regex.search(name):
                    return 'x264'

        elif video_codec == 'H.265':
            for name in _file_and_parent(self._path):
                if self._x265_regex.search(name):
                    return 'x265'

        return video_codec

    def _get_group(self):
        return self._guessit.get('release_group', '')


def _file_and_parent(path):
    """Yield `basename` and `dirname` of `path`"""
    basename = fs.basename(path)
    dirname = os.path.dirname(path)
    yield basename
    if dirname and dirname != basename:
        yield dirname


def _as_list(guess, key):
    value = guess.get(key, None)
    if value is None:
        return []
    elif isinstance(value, str):
        return [value]
    elif isinstance(value, list):
        return list(value)


def _as_str(guess, key):
    return str(guess.get(key, ''))


def _as_str_or_list_of_str(guess, key):
    value = guess.get(key, '')
    if not isinstance(value, str) and isinstance(value, list):
        return [str(v) for v in value]
    return str(value)
