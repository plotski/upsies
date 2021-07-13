"""
Release name parsing and formatting

:class:`ReleaseInfo` parses a string into a dictionary-like object with a
specific set of keys, e.g. "title", "resolution", "source", etc.

:class:`ReleaseName` wraps :class:`ReleaseInfo` to do the same, but in addition
it tries to read media data from the file system to get information. It also
adds a :class:`~.ReleaseName.format` method to turn everything back into a
string.
"""

import collections
import os
import re
import time

import natsort
import unidecode

from .. import constants, errors
from ..utils import scene, webdbs
from . import LazyModule, cached_property, fs, video
from .types import ReleaseType

import logging  # isort:skip
_log = logging.getLogger(__name__)

# Disable debugging messages from rebulk
logging.getLogger('rebulk').setLevel(logging.WARNING)

_guessit = LazyModule(module='guessit.api', name='_guessit', namespace=globals())


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
        self._info = ReleaseInfo(self._path)
        self._imdb = webdbs.imdb.ImdbApi()

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
        :class:`~.types.ReleaseType` enum or one of its value names

        See also :meth:`fetch_info`.
        """
        return self._info.get('type', ReleaseType.unknown)

    @type.setter
    def type(self, value):
        if not value:
            self._info['type'] = ReleaseType.unknown
        else:
            self._info['type'] = ReleaseType(value)

    @property
    def title(self):
        """
        Original name of movie or series or "UNKNOWN_TITLE"

        See also :meth:`fetch_info`.
        """
        return self._info.get('title') or 'UNKNOWN_TITLE'

    @title.setter
    def title(self, value):
        self._info['title'] = str(value)

    @property
    def title_aka(self):
        """
        Alternative name of movie or series or empty string

        For non-English original titles, this should be the English title. If
        :attr:`title` is identical, this is an empty string.

        See also :meth:`fetch_info`.
        """
        aka = self._info.get('aka') or ''
        if aka and aka != self.title:
            return aka
        else:
            return ''

    @title_aka.setter
    def title_aka(self, value):
        self._info['aka'] = str(value)

    @property
    def title_with_aka(self):
        """Combination of :attr:`title` and :attr:`title_aka`"""
        if self.title_aka:
            return f'{self.title} AKA {self.title_aka}'
        else:
            return self.title

    @property
    def title_with_aka_and_year(self):
        """
        Combination of :attr:`title`, :attr:`title_aka` and :attr:`year`

        For movies, the :attr:`year` is always appended to the
        :attr:`title`. For series, the :attr:`year` is appended if
        :attr:`year_required` is `True`.

        :attr:`title_aka` is appended if it is truthy.
        """
        title = [self.title]
        if self.title_aka:
            title.extend(('AKA', self.title_aka))
        if self.year_required:
            title.append(self.year)
        return ' '.join(title)

    @property
    def year(self):
        """
        Release year or "UNKNOWN_YEAR" for movies, empty string for series unless
        :attr:`year_required` is set

        See also :meth:`fetch_info`.
        """
        if self.type is ReleaseType.movie or self.year_required:
            return self._info.get('year') or 'UNKNOWN_YEAR'
        else:
            return self._info.get('year') or ''

    @year.setter
    def year(self, value):
        if not isinstance(value, (str, int)) and value is not None:
            raise TypeError(f'Not a number: {value!r}')
        elif not value:
            self._info['year'] = ''
        else:
            year = str(value)
            current_year = int(time.strftime('%Y')) + 2
            if len(year) != 4 or not year.isdecimal() or not 1880 <= int(year) <= current_year:
                raise ValueError(f'Invalid year: {value}')
            self._info['year'] = year

    @property
    def year_required(self):
        """
        Whether :attr:`title_full` includes :attr:`year`

        See also :meth:`fetch_info`.
        """
        default = self.type is ReleaseType.movie
        return getattr(self, '_year_required', default)

    @year_required.setter
    def year_required(self, value):
        self._year_required = bool(value)

    @property
    def episodes(self):
        """
        Season and episodes in "S01E02"-style format or "UNKNOWN_SEASON" for season
        packs, "UNKNOWN_EPISODE" for episodes, empty string for other types

        This property can be set to one or more season numbers (:class:`str`,
        :class:`int` or sequence of those), a "S01E02"-style string (see
        :meth:`Episodes.from_string`) or any falsy value.
        """
        if self.type is ReleaseType.season:
            return str(self._info.get('episodes') or 'UNKNOWN_SEASON')
        elif self.type is ReleaseType.episode:
            episodes = self._info.get('episodes', Episodes())
            if not any(season for season in episodes.values()):
                return 'UNKNOWN_EPISODE'
            else:
                return str(episodes)
        elif self.type is ReleaseType.unknown:
            return str(self._info.get('episodes') or '')
        else:
            return ''

    @episodes.setter
    def episodes(self, value):
        if isinstance(value, str) and Episodes.has_episodes_info(value):
            self._info['episodes'] = Episodes.from_string(value)
        elif not isinstance(value, str) and isinstance(value, collections.abc.Mapping):
            self._info['episodes'] = Episodes(value)
        elif not isinstance(value, str) and isinstance(value, collections.abc.Iterable):
            self._info['episodes'] = Episodes({v: () for v in value})
        elif value:
            self._info['episodes'] = Episodes({value: ()})
        else:
            self._info['episodes'] = Episodes()

    @property
    def episode_title(self):
        """Episode title if :attr:`type` is "episode" or empty string"""
        if self.type is ReleaseType.episode:
            return self._info.get('episode_title') or ''
        else:
            return ''

    @episode_title.setter
    def episode_title(self, value):
        self._info['episode_title'] = str(value)

    @property
    def service(self):
        """Streaming service abbreviation (e.g. "AMZN", "NF") or empty string"""
        return self._info.get('service') or ''

    @service.setter
    def service(self, value):
        self._info['service'] = str(value)

    @property
    def edition(self):
        """List of "Director's Cut", "Uncut", "Unrated", etc"""
        if 'edition' not in self._info:
            self._info['edition'] = []
        if 'Dual Audio' not in self._info['edition']:
            if self.has_dual_audio:
                self._info['edition'].append('Dual Audio')
        return self._info['edition']

    @edition.setter
    def edition(self, value):
        self._info['edition'] = [str(v) for v in value]

    @property
    def source(self):
        '''Original source (e.g. "BluRay", "WEB-DL") or "UNKNOWN_SOURCE"'''
        return self._info.get('source') or 'UNKNOWN_SOURCE'

    @source.setter
    def source(self, value):
        self._info['source'] = str(value)

    @property
    def resolution(self):
        '''Resolution (e.g. "1080p") or "UNKNOWN_RESOLUTION"'''
        res = video.resolution(self._path)
        if res is None:
            res = self._info.get('resolution') or 'UNKNOWN_RESOLUTION'
        return res

    @resolution.setter
    def resolution(self, value):
        self._info['resolution'] = str(value)

    @property
    def audio_format(self):
        '''Audio format or "UNKNOWN_AUDIO_FORMAT"'''
        af = video.audio_format(self._path)
        if af is None:
            af = self._info.get('audio_codec') or 'UNKNOWN_AUDIO_FORMAT'
        return af

    @audio_format.setter
    def audio_format(self, value):
        self._info['audio_codec'] = str(value)

    @property
    def audio_channels(self):
        """Audio channels (e.g. "5.1") or empty string"""
        ac = video.audio_channels(self._path)
        if ac is None:
            ac = self._info.get('audio_channels') or ''
        return ac

    @audio_channels.setter
    def audio_channels(self, value):
        self._info['audio_channels'] = str(value)

    @property
    def video_format(self):
        '''Video format (or encoder in case of x264/x265/XviD) or "UNKNOWN_VIDEO_FORMAT"'''
        vf = video.video_format(self._path)
        if vf is None:
            vf = self._info.get('video_codec') or 'UNKNOWN_VIDEO_FORMAT'
        return vf

    @video_format.setter
    def video_format(self, value):
        self._info['video_codec'] = str(value)

    @property
    def group(self):
        '''Name of release group or "NOGROUP"'''
        return self._info.get('group') or 'NOGROUP'

    @group.setter
    def group(self, value):
        self._info['group'] = str(value)

    @property
    def has_commentary(self):
        """
        Whether this release has a commentary audio track

        If not set explicitly and the given `path` exists, this value is
        autodetected by looking for "commentary" case-insensitively in any audio
        track title.

        If not set explicitly and the given `path` does not exists, default to
        detection by :class:`ReleaseInfo`.

        Setting this value back to `None` turns on autodetection as described
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
            return self._info.get('has_commentary')

    @has_commentary.setter
    def has_commentary(self, value):
        if value is None:
            self._has_commentary = value
        else:
            self._has_commentary = bool(value)

    @property
    def has_dual_audio(self):
        """
        Whether this release has an English and a non-English, original language
        audio track

        If not set explicitly and the given `path` exists, this value is
        autodetected if possible, otherwise default to whatever
        :class:`ReleaseInfo` detected in the release name.

        Setting this value back to `None` turns on autodetection as described
        above.
        """
        # Use manually set value unless it is None
        if hasattr(self, '_has_dual_audio') and self._has_dual_audio is not None:
            return self._has_dual_audio

        # Autodetect dual audio
        elif os.path.exists(self._path):
            self._has_dual_audio = bool(video.has_dual_audio(self._path))
            return self._has_dual_audio

        # Default to ReleaseInfo['has_dual_audio']
        else:
            return 'Dual Audio' in self._info.get('edition', ())

    @has_dual_audio.setter
    def has_dual_audio(self, value):
        if value is None:
            self._has_dual_audio = value
        else:
            self._has_dual_audio = bool(value)

    _needed_attrs = {
        ReleaseType.movie: ('title', 'year', 'resolution', 'source',
                            'audio_format', 'video_format'),
        ReleaseType.season: ('title', 'episodes', 'resolution', 'source',
                             'audio_format', 'video_format'),
        ReleaseType.episode: ('title', 'episodes', 'resolution', 'source',
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
          - :attr:`type`
          - :attr:`year`
          - :attr:`year_required`
        """
        await self._update_attributes(id)
        await self._update_year_required()
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
            ('year', 'year'),
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

            def normalize_title(title):
                return unidecode.unidecode(title.casefold())

            title_normalized = normalize_title(self.title)
            same_titles = tuple(f'{r.title} year={r.year} id={r.id}' for r in results
                                if normalize_title(r.title) == title_normalized)
            if len(same_titles) >= 2:
                _log.debug('Found multiple search results for %r: %r', query, same_titles)
                self.year_required = True

    def format(self, sep=' '):
        """Assemble all parts into string"""
        parts = [self.title_with_aka_and_year]

        if self.type in (ReleaseType.season, ReleaseType.episode):
            parts.append(str(self.episodes))

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

    :param bool strict: Whether to raise :class:`~.errors.ContentError` if
        `release` looks bad, e.g. an abbreviated scene release file name like
        "tf-foof.mkv"

    If `release` looks like an abbreviated scene file name (e.g.
    "abd-mother.mkv"), the parent directory's name is used if possible.

    Gathered information is provided as a dictionary with the following keys:

      - ``type`` (:class:`~.types.ReleaseType` enum)
      - ``title``
      - ``aka`` (Also Known As; anything after "AKA" in the title)
      - ``year``
      - ``episodes`` (:class:`~.Episodes` instance)
      - ``episode_title``
      - ``edition`` (:class:`list` of "Extended", "Uncut", etc)
      - ``resolution``
      - ``service`` (Streaming service abbreviation)
      - ``source`` ("BluRay", "WEB-DL", etc)
      - ``audio_codec`` (Audio codec abbreviation)
      - ``audio_channels`` (e.g. "2.0" or "7.1")
      - ``video_codec``
      - ``group``
      - ``has_commentary`` (:class:`bool` or `None` to autodetect)

    Unless documented otherwise above, all values are strings. Unknown values
    are empty strings.
    """

    def __init__(self, path, strict=False):
        if strict:
            try:
                scene.assert_not_abbreviated_filename(path)
            except errors.SceneError as e:
                raise errors.ContentError(e)
        self._path = str(path)
        self._abspath = os.path.abspath(self._path)
        self._dict = {}

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

    @property
    def path(self):
        """`path` argument as :class:`str`"""
        return self._path

    @cached_property
    def _guess(self):
        path = self._abspath

        # guessit doesn't detect AC3 if it's called "AC-3"
        path = re.sub(r'([ \.])(?i:AC-?3)([ \.])', r'\1AC3\2', path)
        path = re.sub(r'([ \.])(?i:E-?AC-?3)([ \.])', r'\1EAC3\2', path)

        # _log.debug('Running guessit on %r with %r', path, constants.GUESSIT_OPTIONS)
        guess = dict(_guessit.default_api.guessit(path, options=constants.GUESSIT_OPTIONS))
        # _log.debug('Original guess: %r', guess)

        # We do our own episode parsing to preserve order
        for name in fs.file_and_parent(path):
            if Episodes.has_episodes_info(name):
                guess['episodes'] = Episodes.from_string(name)
                break
        else:
            # Guessit can parse multiple seasons/episodes to some degree
            seasons = _as_list(guess.get('season'))
            episodes = _as_list(guess.get('episode'))
            string = []
            if seasons:
                string.append(f'S{seasons[0]:02d}')
            for e in episodes:
                string.append(f'E{e:02d}')
            guess['episodes'] = Episodes.from_string(''.join(string))

        return guess

    @property
    def _guessit_options(self):
        return _guessit.default_api.advanced_config

    def _get_type(self):
        for name in fs.file_and_parent(self._path):
            if Episodes.has_episodes_info(name):
                episodes = Episodes.from_string(name)
                if any(episodes.values()):
                    return ReleaseType.episode
                else:
                    return ReleaseType.season

        guessit_type = _as_string(self._guess.get('type'))
        if not guessit_type:
            return ReleaseType.unknown
        elif guessit_type == 'episode':
            # guessit doesn't detect season packs; check if at least one episode
            # is specified
            if any(episodes for episodes in self['episodes'].values()):
                return ReleaseType.episode
            else:
                return ReleaseType.season
        else:
            return ReleaseType.movie

    _title_split_regex = re.compile(
        r'[ \.]+(?:'
        r'\d{4}|'  # Year
        r'(?i:[SE]\d+)+|'
        r'((?i:Season|Episode)[ \.]*\d+[ \.]*)+|'
        r')[ \.]+'
    )

    @cached_property
    def release_name_params(self):
        """
        Release name without title and year or season/episode info

        This allows us to find stuff in the release name that guessit doesn't
        support without accidentally finding it in the title.
        """
        path_no_ext = fs.strip_extension(self._abspath, only=constants.VIDEO_FILE_EXTENSIONS)

        # Look for year/season/episode info in file and parent directory name
        for name in fs.file_and_parent(path_no_ext):
            match = self._title_split_regex.search(name)
            if match:
                return self._title_split_regex.split(name, maxsplit=1)[-1]

        # Default to the file/parent that contains either " " or "." (without
        # file extension)
        for name in fs.file_and_parent(path_no_ext):
            if ' ' in name or '.' in name:
                return name

        # Default to file name
        return fs.basename(path_no_ext)

    _title_aka_regex = re.compile(r'[ \.]+AKA[ \.]+')

    @cached_property
    def _title_parts(self):
        # guessit splits AKA at " - ", so we re-join it
        title_parts = [_as_string(self._guess.get('title', ''))]
        if self._guess.get('alternative_title'):
            title_parts.extend(_as_list(self._guess.get('alternative_title')))
        title = ' - '.join(title_parts)
        title_parts = self._title_aka_regex.split(title, maxsplit=1)

        # guessit recognizes mixed seasons and episodes (e.g. "S02E10S03E05") as
        # part of the title.
        def remove_episodes(string):
            return Episodes.regex.sub('', string)

        if len(title_parts) > 1:
            return {'title': remove_episodes(title_parts[0]),
                    'aka': remove_episodes(title_parts[1])}
        else:
            return {'title': remove_episodes(title_parts[0]),
                    'aka': ''}

    def _get_title(self):
        return self._title_parts['title']

    def _get_aka(self):
        return self._title_parts['aka']

    def _get_year(self):
        return _as_string(self._guess.get('year') or '')

    def _get_episodes(self):
        if 'episodes' not in self._guess:
            self._guess['episodes'] = Episodes()
        return self._guess['episodes']

    def _set_episodes(self, value):
        # Keep Episodes() object ID. Ensure `value` is not the object in
        # self._guess['episodes'] so we can clear() without losing items in
        # `value`.
        value = dict(value)
        episodes = self._get_episodes()
        episodes.clear()
        episodes.update(value)

    def _get_episode_title(self):
        return _as_string(self._guess.get('episode_title', ''))

    _edition_translation = {}
    _edition_regex = re.compile(r'(?:[ \.]|^)((?i:proper|repack\d*))(?:[ \.]|$)')

    def _get_edition(self):
        edition = _as_list(self._guess.get('edition'))
        for regex, edition_fixed in self._edition_translation.items():
            for i in range(len(edition)):
                if regex.search(edition[i]):
                    edition[i] = edition_fixed

        # guessit doesn't distinguish between REPACK, PROPER, etc
        match = self._edition_regex.search(self.release_name_params)
        if match:
            edition.append(match.group(1).capitalize())

        guessit_other = _as_list(self._guess.get('other'))
        if 'Dual Audio' in guessit_other:
            edition.append('Dual Audio')
        if 'Open Matte' in guessit_other:
            edition.append('Open Matte')
        if 'Original Aspect Ratio' in guessit_other:
            edition.append('OAR')

        return edition

    def _get_resolution(self):
        return _as_string(self._guess.get('screen_size', ''))

    _streaming_service_regex = re.compile(r'[ \.]([A-Z]+)[ \.](?i:WEB-?(?:DL|Rip))(?:[ \.]|$)')
    _streaming_service_translation = {
        re.compile(r'(?i:IT)') : 'iT',
        # Not a streaming service
        re.compile(r'OAR') : '',  # Original Aspect Ratio
    }

    def _get_service(self):
        def translate(service):
            for regex, abbrev in self._streaming_service_translation.items():
                if regex.search(service):
                    return abbrev
            return service

        service = _as_string(self._guess.get('streaming_service', ''))
        if service:
            # guessit translates abbreviations to full names (NF -> Netflix),
            # but we want abbreviations. Use the same dictionary as guessit.
            translation = self._guessit_options['streaming_service']
            for full_name, aliases in translation.items():
                if service.casefold().strip() == full_name.casefold().strip():
                    # `aliases` is either a string or a list of strings and
                    # other objects.
                    if isinstance(aliases, str):
                        return translate(aliases)
                    else:
                        # Find shortest string
                        aliases = (a for a in aliases if isinstance(a, str))
                        return translate(sorted(aliases, key=len)[0])

        # Default to manual detection
        match = self._streaming_service_regex.search(self.release_name_params)
        if match:
            return translate(match.group(1))

        return ''

    _source_translation = {
        re.compile(r'(?i:blu-?ray)') : 'BluRay',
        re.compile(r'(?i:dvd-?rip)') : 'DVDRip',
        re.compile(r'(?i:web-?dl)')  : 'WEB-DL',
        re.compile(r'(?i:web-?rip)') : 'WEBRip',
        re.compile(r'(?i:web)')      : 'WEB-DL',
    }
    # Look for "Hybrid" after year or season
    _hybrid_regex = re.compile(r'[ \.]hybrid[ \.]', flags=re.IGNORECASE)
    _web_source_regex = re.compile(r'[ \.](WEB-?(?:DL|Rip))(?:[ \.]|$)', flags=re.IGNORECASE)

    def _get_source(self):
        source = self._guess.get('source', '')

        # guessit parses multiple source (e.g. ["WEB", "Blu-ray"]) if it can
        # find them. This is an issue if an episode title contains a "source",
        # e.g. "TC" -> "Telecine".
        if not isinstance(source, str):
            source = source[0]

        if source.lower() == 'web':
            # guessit doesn't distinguish between WEB-DL and WEBRip. Get the
            # source from the path.
            match = self._web_source_regex.search(self.release_name_params)
            if match:
                source = match.group(1)

        elif source == 'DVD':
            # Detect DVDRip
            if 'Rip' in self._guess.get('other', ()):
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

        # Detect Remux and Hybrid
        other = self._guess.get('other', ())
        if 'Remux' in other and 'WEB' not in source and 'Rip' not in source:
            source += ' Remux'
        if 'Hybrid' in other:
            source = 'Hybrid ' + source

        return source

    _audio_codec_translation = {
        re.compile(r'^AC-?3')             : 'AC-3',
        re.compile(r'Dolby Digital$')     : 'AC-3',
        re.compile(r'^E-?AC-?3')          : 'E-AC-3',
        re.compile(r'Dolby Digital Plus') : 'E-AC-3',
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
        audio_codec = _as_string(self._guess.get('audio_codec'))
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
                audio_codec = re.sub(r'(?:E-|)AC-?3 TrueHD', 'TrueHD', audio_codec)
                audio_codec = re.sub(r'(?:E-|)AC-?3 Atmos', 'Atmos', audio_codec)
            else:
                # Codecs like "MP3" or "FLAC" are already abbreviated
                audio_codec = ' '.join(infos)

            return audio_codec

    _audio_channels_regex = re.compile(r'[ \.](\d\.\d)[ \.]')

    def _get_audio_channels(self):
        audio_channels = _as_string(self._guess.get('audio_channels', ''))
        if not audio_channels:
            match = self._audio_channels_regex.search(self.release_name_params)
            if match:
                return match.group(1)
        return audio_channels

    _x264_regex = re.compile(r'(?:^|[\. ])(?i:x264)(?:[\. -]|$)')
    _x265_regex = re.compile(r'(?:^|[\. ])(?i:x265)(?:[\. -]|$)')

    def _get_video_codec(self):
        video_codec = _as_string(self._guess.get('video_codec', ''))
        if video_codec == 'H.264':
            if self._x264_regex.search(self.release_name_params):
                return 'x264'

        elif video_codec == 'H.265':
            if self._x265_regex.search(self.release_name_params):
                return 'x265'

        return video_codec

    def _get_group(self):
        return _as_string(self._guess.get('release_group', ''))

    _has_commentary_regex = re.compile(r'[\. ](?i:plus[\. -]+comm|commentary)[\. -]')

    def _get_has_commentary(self):
        if self._guess.get('has_commentary', None) is None:
            self._guess['has_commentary'] = \
                bool(self._has_commentary_regex.search(self.release_name_params))
        return self._guess['has_commentary']

    def _set_has_commentary(self, value):
        if value is None:
            self._guess['has_commentary'] = None
        else:
            self._guess['has_commentary'] = bool(value)


class Episodes(dict):
    """
    :class:`dict` subclass that maps season numbers to sequences of episode
    numbers

    All keys and values are :class:`str` objects. All episodes from a season are
    indicated by an empty sequence. For episodes from any sason, the key is an
    empty string.
    """

    regex = re.compile(r'(?:^|[\. ])((?i:[SE]\d+)+)(?:[\. ]|$)')
    """Regular expression that matches "S01E02"-like episode information"""

    @classmethod
    def has_episodes_info(cls, string):
        """Whether `string` contains "S01E02"-like episode information"""
        return bool(cls.regex.search(string))

    @classmethod
    def from_string(cls, value):
        """
        Create instance from release name or string that contains "Sxx" and "Exx"

        Examples:

            >>> Episodes.from_string('foo.E01 bar')
            {'': ('1',)}
            >>> Episodes.from_string('foo E01E2.bar')
            {'': ('1', '2')}
            >>> Episodes.from_string('foo.bar.E01E2S03')
            {'': ('1', '2'), '3': ()}
            >>> Episodes.from_string('E01E2S03E04E05.baz')
            {'': ('1', '2'), '3': ('4', '5')}
            >>> Episodes.from_string('S09E08S03E06S9E1')
            {'9': ('1', '8',), '3': ('6',)}
            >>> Episodes.from_string('E01S03E06.bar.E02')
            {'': ('1', '2',), '3': ('6',)}
        """
        seasons = collections.defaultdict(lambda: set())

        def split_episodes(string):
            return {str(int(e)) for e in string.split('E') if e.strip()}

        for word in re.split(r'[ \.]', str(value)):
            word = word.upper()
            if cls.has_episodes_info(word):
                for part in (k for k in word.split('S') if k):
                    season = re.sub(r'E.*$', '', part)
                    season = str(int(season)) if season else ''
                    episodes = re.sub(r'^\d+', '', part)
                    episodes = split_episodes(episodes) if episodes else ()
                    seasons[season].update(episodes)
        args = {season: tuple(natsort.natsorted(episodes))
                for season, episodes in natsort.natsorted(seasons.items())}
        return cls(args)

    @classmethod
    def from_sequence(cls, sequence):
        """
        Combine episode information from multiple strings

        Examples:

            >>> Episodes.from_sequence(['foo.S01E01.bar', 'hello'])
            {'1': ('1',)}
            >>> Episodes.from_sequence(['foo.S01E01.bar', 'bar.S01E02.baz'])
            {'1': ('1', '2')}
        """
        episodes = Episodes()
        for string in sequence:
            eps = cls.from_string(string)
            for season in eps:
                if season in episodes:
                    episodes[season] += eps[season]
                else:
                    episodes[season] = eps[season]
        return episodes

    def __init__(self, *args, **kwargs):
        def number(name, value):
            if isinstance(value, int):
                if value >= 0:
                    return str(value)
                else:
                    raise ValueError(f'Invalid {name}: {value!r}')
            elif isinstance(value, str):
                if value == '' or value.isdigit():
                    return str(value)
                else:
                    raise ValueError(f'Invalid {name}: {value!r}')
            else:
                raise TypeError(f'Invalid {name}: {value!r}')

        validated_args = {}
        for season, episodes in dict(*args, **kwargs).items():
            season = number('season', season)
            if not isinstance(episodes, collections.abc.Iterable):
                raise TypeError(f'Invalid episodes: {episodes!r}')
            else:
                episodes = tuple(number('episode', e) for e in episodes)
            validated_args[season] = episodes
        return super().__init__(validated_args)

    def remove_specific_episodes(self):
        """Remove episodes from each season, leaving only complete season"""
        for season in tuple(self):
            if season:
                self[season] = ()
            else:
                del self[season]

    def __repr__(self):
        return f'{type(self).__name__}({dict(self)!r})'

    def __str__(self):
        parts = []
        for season, episodes in sorted(self.items()):
            if season:
                parts.append(f'S{season:0>2}')
            for episode in episodes:
                parts.append(f'E{episode:0>2}')
        return ''.join(parts)


def _as_list(value):
    if not value:
        return []
    elif isinstance(value, str):
        return [value]
    elif isinstance(value, list):
        return list(value)
    else:
        return [value]

def _as_string(value):
    if not value:
        return ''
    elif isinstance(value, str):
        return value
    elif isinstance(value, list):
        return ' '.join(value)
    else:
        return str(value)
