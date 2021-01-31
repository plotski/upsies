"""
Release name parsing and formatting

:class:`ReleaseInfo` parses a string into a dictionary-like object with a
specific set of keys, e.g. "title", "resolution", "source", etc.

:class:`ReleaseName` wraps :class:`ReleaseInfo` to do the same, but in addition
it tries to read media data from the file system to get information. It also
adds a :class:`~.ReleaseName.format` method to turn everything back into a
string.
"""

import asyncio
import collections
import os
import re

from .. import constants, errors
from ..utils import scene, webdbs
from . import LazyModule, cached_property, fs, video
from .types import ReleaseType

import logging  # isort:skip
_log = logging.getLogger(__name__)

# Disable debugging messages from rebulk
logging.getLogger('rebulk').setLevel(logging.WARNING)

_guessit = LazyModule(module='guessit', name='_guessit', namespace=globals())


class ReleaseName(collections.abc.Mapping):
    """
    Standardized release name

    :param str path: Path to release content

    If `path` exists, it is used to analyze file contents for some parts of the
    new release name, e.g. to detect the resolution.

    Example:

    >>> rn = ReleaseName("The.Foo.1984.1080p.Blu-ray.X264-ASDF")
    >>> rn.source
    'BluRay'
    >>> rn.format()
    'The Foo 1984 1080p BluRay DTS x264-ASDF'
    >>> "{title} ({year})".format(**rn)
    'The Foo (1984)'
    """

    def __init__(self, path):
        self._path = str(path)
        self._guess = ReleaseInfo(self._path)
        self._imdb = webdbs.imdb.ImdbApi()
        # FIXME: Getting metainfo (e.g. resolution) can block for several
        #        seconds because utils.videos gets the length of every video
        #        file in a directory to avoid junk (e.g. samples). To reduce
        #        delays while the user is waiting, we're getting all the
        #        information ASAP in an async background thread.
        asyncio.get_event_loop().run_in_executor(None, self._tracks)

    def _tracks(self):
        # Ignore non-existing files and other file system issues
        try:
            return video.tracks(self._path)
        except errors.ContentError:
            return {}

    def __repr__(self):
        return f'{type(self).__name__}({self._path!r})'

    def __str__(self):
        return self.format()

    def __len__(self):
        return len(tuple(iter(self)))

    def __iter__(self):
        # Non-private properties are dictionary keys
        cls = type(self)
        return iter(attr for attr in dir(self)
                    if (not attr.startswith('_')
                        and isinstance(getattr(cls, attr), property)))

    def __getitem__(self, name):
        if not isinstance(name, str):
            raise TypeError(f'Not a string: {name!r}')
        elif isinstance(getattr(type(self), name), property):
            return getattr(self, name)
        else:
            raise KeyError(name)

    @property
    def type(self):
        """
        :class:`~.utils.ReleaseType` enum or one of its value names

        See also :meth:`fetch_info`.
        """
        return self._guess.get('type', ReleaseType.unknown)

    @type.setter
    def type(self, value):
        if not value:
            self._guess['type'] = ReleaseType.unknown
        else:
            self._guess['type'] = ReleaseType(value)

    @property
    def title(self):
        """
        Original name of movie or series or "UNKNOWN_TITLE"

        See also :meth:`fetch_info`.
        """
        return self._guess.get('title') or 'UNKNOWN_TITLE'

    @title.setter
    def title(self, value):
        self._guess['title'] = str(value)

    @property
    def title_aka(self):
        """
        Alternative name of movie or series or empty string

        For non-English original titles, this should be the English title. If
        :attr:`title` is identical, this is an empty string.

        See also :meth:`fetch_info`.
        """
        aka = self._guess.get('aka') or ''
        if aka and aka != self.title:
            return aka
        else:
            return ''

    @title_aka.setter
    def title_aka(self, value):
        self._guess['aka'] = str(value)

    @property
    def year(self):
        """
        Release year or "UNKNOWN_YEAR" for movies, empty string for series unless
        :attr:`year_required` is set

        See also :meth:`fetch_info`.
        """
        if self.type is ReleaseType.movie or self.year_required:
            return self._guess.get('year') or 'UNKNOWN_YEAR'
        else:
            return self._guess.get('year') or ''

    @year.setter
    def year(self, value):
        if not isinstance(value, (str, int)) and value is not None:
            raise TypeError(f'Not a number: {value!r}')
        elif not value:
            self._guess['year'] = ''
        else:
            year = str(value)
            if len(year) != 4 or not year.isdecimal() or not 1800 < int(year) < 2100:
                raise ValueError(f'Invalid year: {value}')
            self._guess['year'] = year

    @property
    def year_required(self):
        """
        Whether release year is needed to make :attr:`title` of TV series unique

        If set to `True`, :meth:`format` appends :attr:`year` after
        :attr:`title` even if :attr:`type` is not :attr:`ReleaseType.movie`.

        For movies, this property should have no effect.

        See also :meth:`fetch_info`.
        """
        return getattr(self, '_year_required', False)

    @year_required.setter
    def year_required(self, value):
        self._year_required = bool(value)

    @property
    def season(self):
        """Season number, "UNKNOWN_SEASON" for series or empty string for movies"""
        if self.type in (ReleaseType.season, ReleaseType.episode, ReleaseType.unknown):
            if self.type is ReleaseType.unknown:
                return self._guess.get('season') or ''
            else:
                return self._guess.get('season') or 'UNKNOWN_SEASON'
        else:
            return ''

    @season.setter
    def season(self, value):
        try:
            self._guess['season'] = self._season_or_episode_number(value)
        except ValueError:
            raise ValueError(f'Invalid season: {value!r}')
        except TypeError:
            raise TypeError(f'Invalid season: {value!r}')

    @property
    def episode(self):
        """Episode number or empty string"""
        if self.type is ReleaseType.episode:
            return self._guess.get('episode') or 'UNKNOWN_EPISODE'
        elif self.type in (ReleaseType.season, ReleaseType.unknown):
            return self._guess.get('episode') or ''
        else:
            return ''

    @episode.setter
    def episode(self, value):
        try:
            if isinstance(value, collections.abc.Sequence) and not isinstance(value, str):
                self._guess['episode'] = [self._season_or_episode_number(e)
                                          for e in value]
            else:
                self._guess['episode'] = self._season_or_episode_number(value)
        except ValueError:
            raise ValueError(f'Invalid episode: {value!r}')
        except TypeError:
            raise TypeError(f'Invalid episode: {value!r}')

    @staticmethod
    def _season_or_episode_number(value):
        if isinstance(value, int):
            if value >= 0:
                return str(value)
            else:
                raise ValueError(f'Invalid value: {value!r}')
        elif isinstance(value, str):
            if (value == '' or value.isdigit()):
                return str(value)
            else:
                raise ValueError(f'Invalid value: {value!r}')
        else:
            raise TypeError(f'Invalid value: {value!r}')

    @property
    def episode_title(self):
        """Episode title if :attr:`type` is "episode" or empty string"""
        if self.type is ReleaseType.episode:
            return self._guess.get('episode_title') or ''
        else:
            return ''

    @episode_title.setter
    def episode_title(self, value):
        self._guess['episode_title'] = str(value)

    @property
    def service(self):
        """Streaming service abbreviation (e.g. "AMZN", "NF") or empty string"""
        return self._guess.get('service') or ''

    @service.setter
    def service(self, value):
        self._guess['service'] = str(value)

    @property
    def edition(self):
        """List of "DC", "Uncut", "Unrated", etc"""
        if 'edition' not in self._guess:
            self._guess['edition'] = []
        return self._guess['edition']

    @edition.setter
    def edition(self, value):
        self._guess['edition'] = [str(v) for v in value]

    @property
    def source(self):
        '''Original source (e.g. "BluRay", "WEB-DL") or "UNKNOWN_SOURCE"'''
        return self._guess.get('source') or 'UNKNOWN_SOURCE'

    @source.setter
    def source(self, value):
        self._guess['source'] = str(value)

    @property
    def resolution(self):
        '''Resolution (e.g. "1080p") or "UNKNOWN_RESOLUTION"'''
        res = video.resolution(self._path)
        if res is None:
            res = self._guess.get('resolution') or 'UNKNOWN_RESOLUTION'
        return res

    @resolution.setter
    def resolution(self, value):
        self._guess['resolution'] = str(value)

    @property
    def audio_format(self):
        '''Audio format or "UNKNOWN_AUDIO_FORMAT"'''
        af = video.audio_format(self._path)
        if af is None:
            af = self._guess.get('audio_codec') or 'UNKNOWN_AUDIO_FORMAT'
        return af

    @audio_format.setter
    def audio_format(self, value):
        self._guess['audio_codec'] = str(value)

    @property
    def audio_channels(self):
        """Audio channels (e.g. "5.1") or empty string"""
        ac = video.audio_channels(self._path)
        if ac is None:
            ac = self._guess.get('audio_channels') or ''
        return ac

    @audio_channels.setter
    def audio_channels(self, value):
        self._guess['audio_channels'] = str(value)

    @property
    def video_format(self):
        '''Video format (or encoder in case of x264/x265/XviD) or "UNKNOWN_VIDEO_FORMAT"'''
        vf = video.video_format(self._path)
        if vf is None:
            vf = self._guess.get('video_codec') or 'UNKNOWN_VIDEO_FORMAT'
        return vf

    @video_format.setter
    def video_format(self, value):
        self._guess['video_codec'] = str(value)

    @property
    def group(self):
        '''Name of release group or "NOGROUP"'''
        return self._guess.get('group') or 'NOGROUP'

    @group.setter
    def group(self, value):
        self._guess['group'] = str(value)

    @property
    def has_commentary(self):
        """
        Whether this release has a commentary audio track

        If not set explicitly and the given `path` exists, this value is
        auto-detected by looking for "commentary" case-insensitively in an audio
        track title.

        If not set explicitly and the given `path` does not exists, default to
        detection by :class:`ReleaseInfo`.

        Setting this value back to `None` turns on auto-detection as described
        above.
        """
        # Use manually set value unless it is None
        if hasattr(self, '_has_commentary') and self._has_commentary is not None:
            return self._has_commentary

        # Find "Commentary" in audio track titles
        elif os.path.exists(self._path):
            tracks = self._tracks()
            for track in tracks.get('Audio', {}):
                if 'commentary' in track.get('Title', '').lower():
                    return True
            return False

        # Default to ReleaseInfo['has_commentary']
        else:
            return self._guess.get('has_commentary')

    @has_commentary.setter
    def has_commentary(self, value):
        if value is None:
            self._has_commentary = value
        else:
            self._has_commentary = bool(value)

    _needed_attrs = {
        ReleaseType.movie: ('title', 'year', 'resolution', 'source',
                            'audio_format', 'video_format'),
        ReleaseType.season: ('title', 'season', 'resolution', 'source',
                             'audio_format', 'video_format'),
        ReleaseType.episode: ('title', 'season', 'episode', 'resolution', 'source',
                              'audio_format', 'video_format'),
    }

    @property
    def is_complete(self):
        """
        Whether all needed information is known and the string returned by
        :meth:`format` will not contain "UNKNOWN_*"

        This always returns `False` if :attr:`type` is
        :attr:`~.ReleaseType.unknown`.
        """
        if self.type is ReleaseType.unknown:
            return False
        for attr in self._needed_attrs[self.type]:
            if self[attr].startswith('UNKNOWN_'):
                return False
        return True

    async def fetch_info(self, id, callback=None):
        """
        Fill in information from IMDb

        :param str id: IMDb ID
        :param callable callback: Function to call after fetching; gets the
            instance (`self`) as a keyword argument

        This coroutine function tries to set these attributes:

          - :attr:`title`
          - :attr:`title_aka`
          - :attr:`year`
          - :attr:`year_required`
        """
        await asyncio.gather(
            self._update_attributes(id),
            self._update_year_required(),
        )
        _log.debug('Release name updated: %s', self)
        if callback is not None:
            callback(self)

    async def _update_attributes(self, id):
        info = await self._imdb.gather(
            id,
            'type',
            'title_english',
            'title_original',
            'year',
        )
        for attr, key in (
                ('title', 'title_original'),
                ('title_aka', 'title_english'),
                ('year', 'year')
        ):
            # Only overload non-empty values
            if info[key]:
                setattr(self, attr, info[key])

        # Use type from IMDb if known. ReleaseInfo can misdetect type (e.g. if
        # mini-series doesn't contain "S01"). But if ReleaseInfo detected an
        # episode (e.g. "S04E03"), it's unlikely to be wrong.
        if info['type'] and self.type is not ReleaseType.episode:
            self.type = info['type']

    async def _update_year_required(self):
        if self.type in (ReleaseType.season, ReleaseType.episode):
            # Find out if there are multiple series with this title
            query = webdbs.Query(title=self.title, type=ReleaseType.series)
            results = await self._imdb.search(query)
            same_titles = tuple(f'{r.title} ({r.year})' for r in results
                                if r.title.casefold() == self.title.casefold())
            _log.debug('Found multiple search results for %r: %r', query, same_titles)
            if len(same_titles) >= 2:
                self.year_required = True
            else:
                self.year_required = False

    def format(self, aka=True, aka_first=False, sep=' '):
        """
        Assemble all the parts into a string
        """
        parts = [self.title]
        if (aka or aka_first) and self.title_aka:
            if aka_first:
                parts[0:0] = (self.title_aka, 'AKA')
            else:
                parts[1:] = ('AKA', self.title_aka)

        if self.type is ReleaseType.movie:
            parts.append(self.year)

        elif self.type in (ReleaseType.season, ReleaseType.episode):
            if self.year_required:
                parts.append(self.year)
            if self.type is ReleaseType.season:
                parts.append(f'S{self.season.rjust(2, "0")}')
            elif self.type is ReleaseType.episode:
                # Episode may be multiple numbers, e.g. for double-long pilots
                if not isinstance(self.episode, str):
                    episode_string = ''.join(f'E{e.rjust(2, "0")}' for e in self.episode)
                else:
                    episode_string = ''.join(f'E{self.episode.rjust(2, "0")}')
                parts.append(f'S{self.season.rjust(2, "0")}{episode_string}')

        if self.edition:
            parts.append(' '.join(self.edition))

        parts.append(self.resolution)

        if self.service:
            parts.append(self.service)
        parts.append(self.source)

        parts.append(self.audio_format)
        if self.audio_channels:
            parts.append(self.audio_channels)
        parts.append(self.video_format)

        return sep.join(parts) + f'-{self.group}'


class ReleaseInfo(collections.abc.MutableMapping):
    """
    Parse information from release name or path

    .. note::

       Consider using :class:`~.ReleaseName` instead to get more accurate info
       from the data of existing files.

    :param str release: Release name or path to release content

    If `release` looks like an abbreviated scene file name (e.g.
    "abd-mother.mkv"), the parent directory's name is used if possible.

    Gathered information is provided as a dictionary with the following keys:

      - ``type`` (:class:`~.utils.ReleaseType` enum)
      - ``title``
      - ``aka`` (Also Known As; anything after "AKA" in the title)
      - ``year``
      - ``season``
      - ``episode`` (:class:`str` or :class:`list` for multi-episodes,
        e.g. "S01E01E02" -> ["1", "2"])
      - ``episode_title``
      - ``edition`` (:class:`list` of "Extended", "Uncut", etc)
      - ``resolution``
      - ``service`` (Streaming service abbreviation)
      - ``source`` ("BluRay", "WEB-DL", etc)
      - ``audio_codec`` (Audio codec abbreviation)
      - ``audio_channels`` (e.g. "2.0" or "7.1")
      - ``video_codec``
      - ``group``
      - ``has_commentary`` (:class:`bool` or `None` to auto-detect)

    Unless documented otherwise above, all values are strings. Unknown values
    are empty strings.
    """

    def __init__(self, path):
        self._path = str(path)
        self._abspath = os.path.abspath(self._path)
        self._dict = {}

    @cached_property
    def _guessit(self):
        if scene.is_abbreviated_filename(self._path):
            _log.debug('Avoiding abbreviated file name: %r', os.path.basename(self._path))
            path = os.path.dirname(self._abspath)
        else:
            path = self._abspath

        # guessit doesn't detect AC3 if it's called "AC-3"
        path = re.sub(r'([ \.])(?i:AC-?3)([ \.])', r'\1AC3\2', path)
        path = re.sub(r'([ \.])(?i:E-?AC-?3)([ \.])', r'\1EAC3\2', path)

        _log.debug('Running guessit on %r', path)
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
        elif hasattr(self, f'_set_{name}'):
            self._dict[name] = getattr(self, f'_set_{name}')(value)
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

    def __repr__(self):
        return f'{type(self).__name__}({self._path!r})'

    def _get_type(self):
        guessit_type = self._guessit.get('type')
        if not guessit_type:
            return ReleaseType.unknown
        elif guessit_type == 'episode':
            # guessit doesn't detect season packs; check if episode is known
            if self._guessit.get('episode'):
                return ReleaseType.episode
            else:
                return ReleaseType.season
        else:
            return ReleaseType.movie

    _title_split_regex = re.compile(
        r'[ \.]+(?:'
        r'\d{4}|'
        r'S\d{2,}(?:E\d{2,})*|'
        r'Season[ \.]*\d+(?:[ \.]Episode[ \.]*\d+)*'
        r')[ \.]+'
    )

    @cached_property
    def release_name_params(self):
        """
        Release name without title and year or season/episode info

        guessit doesn't support some tags like "Hybrid", but we can't just look
        for "Hybrid" anywhere in the release name because it might be part of
        the title or it might be part of the parent directory name.
        """
        path_no_ext = fs.strip_extension(self._abspath, only=constants.VIDEO_FILE_EXTENSIONS)

        # Look for year/season/episode info in file and parent directory name
        for name in _file_and_dir(path_no_ext):
            match = self._title_split_regex.search(name)
            if match:
                return self._title_split_regex.split(name, maxsplit=1)[-1]

        # Default to the file/parent that contains either " " or "." (without
        # file extension)
        for name in _file_and_dir(path_no_ext):
            if ' ' in name or '.' in name:
                return name

        # Default to file name
        return fs.basename(path_no_ext)

    _title_aka_regex = re.compile(r' +AKA +')

    @cached_property
    def _title_parts(self):
        # guessit is very lenient when parsing the title. Try to be more strict
        # by declaring everything before the year or season/episode as title.
        # Try this for the file name first and then the parent directory name.
        title = ''
        for name in _file_and_dir(self._abspath):
            match = self._title_split_regex.search(name)
            if match:
                title = self._title_split_regex.split(name, maxsplit=1)[0].replace('.', ' ')
                break

        # Default to guessit if there is no year/season/episode info.
        if not title:
            # guessit splits the title at " - "
            title_parts = [self._guessit.get('title', '')]
            if self._guessit.get('alternative_title'):
                title_parts.extend(_as_list(self._guessit, 'alternative_title'))
            title = ' - '.join(title_parts)

        # Detect alternative title
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

    _unrated_regex = re.compile(r'[ \.]unrated[ \.]', flags=re.IGNORECASE)

    def _get_edition(self):
        editions = _as_list(self._guessit, 'edition')
        # guessit doesn't always detect "Unrated", e.g. when it comes after "Hybrid"
        if self._unrated_regex.search(self.release_name_params):
            editions.append('Unrated')
        return editions

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
        re.compile(r'(?i:Crackle)')              : 'CRKL',
    }
    _streaming_service_regex = re.compile(r'[ \.]([A-Z]+)[ \.](?i:WEB-?(?:DL|Rip))(?:[ \.]|$)')

    def _get_service(self):
        service = self._guessit.get('streaming_service', '')
        if not service:
            match = self._streaming_service_regex.search(self.release_name_params)
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
    # Look for "Hybrid" after year or season
    _hybrid_regex = re.compile(r'[ \.]hybrid[ \.]', flags=re.IGNORECASE)
    _web_source_regex = re.compile(r'[ \.](WEB-?(?:DL|Rip))(?:[ \.]|$)', flags=re.IGNORECASE)

    def _get_source(self):
        source = self._guessit.get('source', '')
        if source.lower() == 'web':
            # guessit doesn't distinguish between WEB-DL and WEBRip
            match = self._web_source_regex.search(self.release_name_params)
            if match:
                source = match.group(1)

            # Guess WEBRip and WEB-DL based on encoder
            if source.lower() == 'web':
                video_format = video.video_format(self._path)
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
                if 'DVD9' in self.release_name_params:
                    source = 'DVD9'
                elif 'DVD5' in self.release_name_params:
                    source = 'DVD5'

        if source:
            # Fix spelling
            for regex,source_fixed in self._source_translation.items():
                if regex.search(source):
                    source = source_fixed
                    break

        # guessit ignores "Hybrid"
        if self._hybrid_regex.search(self.release_name_params):
            source = ('Hybrid ' + source).strip()

        # Detect Remux
        if 'Remux' in self._guessit.get('other', ()):
            if not any(s in source for s in ('WEBRip', 'WEB-DL')):
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

    _audio_channels_regex = re.compile(r'[ \.](\d\.\d)[ \.]')

    def _get_audio_channels(self):
        audio_channels = self._guessit.get('audio_channels', '')
        if not audio_channels:
            match = self._audio_channels_regex.search(self.release_name_params)
            if match:
                return match.group(1)
        return audio_channels

    _x264_regex = re.compile(r'[\. ](?i:x264)(?:[\. -]|$)')
    _x265_regex = re.compile(r'[\. ](?i:x265)(?:[\. -]|$)')

    def _get_video_codec(self):
        video_codec = self._guessit.get('video_codec', '')
        if video_codec == 'H.264':
            if self._x264_regex.search(self.release_name_params):
                return 'x264'

        elif video_codec == 'H.265':
            if self._x265_regex.search(self.release_name_params):
                return 'x265'

        return video_codec

    def _get_group(self):
        return self._guessit.get('release_group', '')

    _has_commentary_regex = re.compile(r'[\. ](?i:plus[\. -]+comm|commentary)[\. -]')

    def _get_has_commentary(self):
        if self._guessit.get('has_commentary', None) is None:
            self._guessit['has_commentary'] = \
                bool(self._has_commentary_regex.search(self.release_name_params))
        return self._guessit['has_commentary']

    def _set_has_commentary(self, value):
        if value is None:
            self._guessit['has_commentary'] = None
        else:
            self._guessit['has_commentary'] = bool(value)

    @property
    def season_and_episode(self):
        """
        Season and episode as formatted in release names (e.g. "S04", "S04E03")

        Empty string if ``season`` is not specified.
        """
        season = self['season']
        if season:
            season_episode = f'S{season:0>2}'
            episode = self['episode']
            if episode:
                if isinstance(episode, str):
                    # Single episode
                    season_episode += f'E{episode:0>2}'
                else:
                    # Multi-episode (e.g. "S01E01E02")
                    season_episode += ''.join((f'E{e:0>2}' for e in episode))
            return season_episode
        else:
            return ''


def _file_and_dir(path):
    """Return `path`'s filename and parent directoy name"""
    filename = fs.basename(path)
    dirname = fs.basename(os.path.dirname(path))
    names = []
    if not scene.is_abbreviated_filename(filename):
        names.append(filename)
    if dirname and dirname != filename:
        names.append(dirname)
    if not names:
        # Default to garbled filename
        names.append(filename)
    return names


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
