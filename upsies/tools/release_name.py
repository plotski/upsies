import asyncio
import collections

from ..utils import guessit
from . import dbs, mediainfo

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ReleaseName(collections.abc.Mapping):
    """
    Extract information from release name and re-assemble it

    :param str path: Path to release content

    Example:

    >>> rn = ReleaseName("The Foo 1984 1080p BluRay DTS-ASDF")
    >>> rn.source
    'BluRay'
    >>> "{title} ({year})".format(**rn)
    'The Foo (1984)'
    """

    def __init__(self, path):
        self._path = str(path)
        self._guess = guessit.guessit(self._path)

    def __repr__(self):
        return f'{type(self).__name__}({self._path!r})'

    def __str__(self):
        return self.format()

    def __len__(self):
        return len(self.format())

    def __iter__(self):
        # Non-private properties are dictionary keys
        cls = type(self)
        return iter(attr for attr in dir(self)
                    if (not attr.startswith('_')
                        and isinstance(getattr(cls, attr), property)))

    def __getitem__(self, name):
        if not isinstance(name, str):
            raise TypeError(f'Not a string: {name!r}')

        if isinstance(getattr(type(self), name), property):
            return getattr(self, name)
        else:
            raise KeyError(name)

    @property
    def type(self):
        '''"movie", "season", "episode" or empty string'''
        return self._guess.get('type', '')

    @type.setter
    def type(self, value):
        if value not in ('movie', 'season', 'episode', ''):
            raise ValueError(f'Invalid type: {value!r}')
        self._guess['type'] = value

    @property
    def title(self):
        '''Original name of movie or series or "UNKNOWN_TITLE"'''
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
        """Release year or "UNKNOWN_YEAR" for movies, empty string for series"""
        if self.type == 'movie' or self.year_required:
            return self._guess.get('year') or 'UNKNOWN_YEAR'
        else:
            return self._guess.get('year') or ''

    @year.setter
    def year(self, value):
        if not isinstance(value, (str, int)):
            raise TypeError(f'Not a number: {value!r}')
        self._guess['year'] = str(value)

    @property
    def year_required(self):
        """
        Whether release year is needed to make :attr:`title` unique

        For TV series, :attr:`year` should only be added to the release name if
        multiple series with the same title exist.

        This property is set by :meth:`fetch_info`.
        """
        return getattr(self, '_year_required', False)

    @year_required.setter
    def year_required(self, value):
        self._year_required = bool(value)

    @property
    def season(self):
        """Season number, "UNKNOWN_SEASON" for series or empty string for movies"""
        if self.type in ('season', 'episode'):
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
        if self.type in ('season', 'episode'):
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
        if self.type == 'episode':
            return self._guess.get('episode_title') or ''
        else:
            return ''

    @episode_title.setter
    def episode_title(self, value):
        self._guess['episode_title'] = str(value)

    @property
    def service(self):
        """Service abbreviation (e.g. "AMZN", "NF") or empty string"""
        return self._guess.get('streaming_service') or ''

    @service.setter
    def service(self, value):
        self._guess['streaming_service'] = str(value)

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
        res = mediainfo.resolution(self._path)
        if res is None:
            res = self._guess.get('screen_size') or 'UNKNOWN_RESOLUTION'
        return res

    @resolution.setter
    def resolution(self, value):
        self._guess['screen_size'] = str(value)

    @property
    def audio_format(self):
        '''Audio format or "UNKNOWN_AUDIO_FORMAT"'''
        af = mediainfo.audio_format(self._path)
        if af is None:
            af = self._guess.get('audio_codec') or 'UNKNOWN_AUDIO_FORMAT'
        return af

    @audio_format.setter
    def audio_format(self, value):
        self._guess['audio_codec'] = str(value)

    @property
    def audio_channels(self):
        """Audio channels (e.g. "5.1") or empty string"""
        ac = mediainfo.audio_channels(self._path)
        if ac is None:
            ac = self._guess.get('audio_channels') or ''
        return ac

    @audio_channels.setter
    def audio_channels(self, value):
        self._guess['audio_channels'] = str(value)

    @property
    def video_format(self):
        '''Video format (or encoder in case of x264/x265/XviD) or "UNKNOWN_VIDEO_FORMAT"'''
        vf = mediainfo.video_format(self._path)
        if vf is None:
            vf = self._guess.get('video_codec') or 'UNKNOWN_VIDEO_FORMAT'
        return vf

    @video_format.setter
    def video_format(self, value):
        self._guess['video_codec'] = str(value)

    @property
    def group(self):
        '''Name of release group or "NOGROUP"'''
        return self._guess.get('release_group') or 'NOGROUP'

    @group.setter
    def group(self, value):
        self._guess['release_group'] = str(value)

    async def fetch_info(self, id, callback=None):
        """
        Fill in information from online database

        :param str id: ID to query `db` for
        :param callable callback: Function to call after fetching; gets the
            instance (`self`) as a keyword argument

        Calling this coroutine function overrides these attributes:

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
        info = await dbs.imdb.info(
            id,
            dbs.imdb.type,
            dbs.imdb.title_english,
            dbs.imdb.title_original,
            dbs.imdb.year,
        )
        for attr, key in (
                ('title', 'title_original'),
                ('title_aka', 'title_english'),
                ('year', 'year')
        ):
            # Test that "no info" doesn't overload existing attrs
            if info[key]:
                setattr(self, attr, info[key])

        # guessit can misdetect type (e.g. if mini-series doesn't contain
        # "S01"). But if guessit detected an episode (e.g. "S04E03"), it's
        # unlikely to be wrong. Also, `id` could be the ID for the whole
        # "series" or a single "episode".
        if self.type != 'episode':
            self.type = info['type']

    async def _update_year_required(self):
        if self.type in ('season', 'episode'):
            # Find out if there are multiple series with this title
            results = await dbs.imdb.search(dbs.Query(title=self.title,
                                                      type='series'))
            same_titles = tuple(
                r for r in results
                if r.title.casefold() == self.title.casefold()
            )
            _log.debug('Found multiple search results for %r', same_titles)
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

        if self.type == 'movie':
            parts.append(self.year)

        elif self.type in ('season', 'episode'):
            if self.year_required:
                parts.append(self.year)
            if self.type == 'season':
                parts.append(f'S{self.season.rjust(2, "0")}')
            elif self.type == 'episode':
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
