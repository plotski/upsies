from . import guessit, mediainfo

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ReleaseName:
    """Properly formatted release name"""

    def __init__(self, path):
        self._path = str(path)
        self._guess = guessit.guessit(self._path)

    def __repr__(self):
        return f'{type(self).__name__}({self._path!r})'

    def __str__(self):
        return self.format()

    def __len__(self):
        return len(self.format())

    def format(self, aka=True, aka_first=False, sep=' '):
        parts = [self.title]
        if (aka or aka_first) and self.title_aka:
            if aka_first:
                parts.insert(0, f'{self.title_aka} AKA')
            else:
                parts.append(f'AKA {self.title_aka}')

        if self.type == 'movie':
            parts.append(self.year)

        elif self.type in ('season', 'episode'):
            # TODO: Find out if we need to include the year
            if self.type == 'season':
                parts.append(f'S{self.season.rjust(2, "0")}')
            elif self.type == 'episode':
                parts.append(f'S{self.season.rjust(2, "0")}E{self.episode.rjust(2, "0")}')

        if self.edition:
            parts.append(self.edition)

        parts.append(self.resolution)

        if self.service:
            parts.append(self.service)
        parts.append(self.source)

        parts.append(self.audio_format)
        if self.audio_channels:
            parts.append(self.audio_channels)
        parts.append(self.video_format)

        return sep.join(parts) + f'-{self.group}'

    def __getitem__(self, name):
        if not isinstance(name, str):
            raise TypeError(f'Not a string: {name!r}')
        try:
            return getattr(self, name)
        except AttributeError:
            raise KeyError(name)

    @property
    def type(self):
        '''"movie", "season" or "episode"'''
        return self._guess['type']

    @type.setter
    def type(self, value):
        if value not in ('movie', 'season', 'episode'):
            raise ValueError('Must be one of ("movie", "season", "episode"): {value!r}')
        self._guess['type'] = value

    @property
    def title(self):
        '''Movie or series name or "UNKNOWN_TITLE"'''
        return self._guess.get('title') or 'UNKNOWN_TITLE'

    @title.setter
    def title(self, value):
        self._guess['title'] = str(value)

    @property
    def title_aka(self):
        """
        Alternative name of movie or series or empty string

        For non-English titles, this should be the English title. If
        :attr:`title` is identical, this is an empty string.
        """
        aka = self._guess.get('alternative_title') or ''
        if aka and aka != self.title:
            return aka
        else:
            return ''

    @title_aka.setter
    def title_aka(self, value):
        self._guess['alternative_title'] = str(value) if value else ''

    @property
    def title_english(self):
        '''English title of movie or series or "UNKNOWN_TITLE"'''
        return self._guess.get('english_title') or 'UNKNOWN_TITLE'

    @title_english.setter
    def title_english(self, value):
        self._guess['alternative_title'] = str(value) if value else ''

    @property
    def year(self):
        """Release year, "UNKNOWN_YEAR" for movies or empty string for series"""
        if self.type == 'movie':
            return self._guess.get('year') or 'UNKNOWN_YEAR'
        else:
            return self._guess.get('year') or ''

    @year.setter
    def year(self, value):
        if not isinstance(value, (str, int)):
            raise TypeError('Not a number: {value!r}')
        self._guess['year'] = str(value)

    @property
    def season(self):
        """Season number, "UNKNOWN_SEASON" for series or empty string for movies"""
        if self.type == 'movie':
            return ''
        else:
            return self._guess.get('season') or 'UNKNOWN_SEASON'

    @season.setter
    def season(self, value):
        if not isinstance(value, (str, int)):
            raise TypeError('Not a number: {value!r}')
        elif not value:
            self._guess['season'] = ''
        else:
            self._guess['season'] = str(value)

    @property
    def episode(self):
        """Episode number or empty string"""
        return self._guess.get('episode') or ''

    @episode.setter
    def episode(self, value):
        if value and not isinstance(value, (str, int)):
            raise TypeError('Not a number: {value!r}')
        self._guess['episode'] = str(value) if value else ''

    @property
    def episode_title(self):
        """Episode title or empty string"""
        return self._guess.get('episode_title') or ''

    @episode_title.setter
    def episode_title(self, value):
        self._guess['episode_title'] = str(value) if value else ''

    @property
    def service(self):
        """Service abbreviation (e.g. "AMZN", "NF") or empty string"""
        return self._guess.get('streaming_service') or ''

    @service.setter
    def service(self, value):
        self._guess['streaming_service'] = str(value) if value else ''

    @property
    def edition(self):
        """Edition (e.g. "Unrated") or empty string"""
        return ' '.join(self._guess.get('edition', ()))

    @edition.setter
    def edition(self, value):
        self._guess['edition'] = list(value) if value else ''

    @property
    def source(self):
        '''Original source (e.g. "BluRay", "WEB-DL") or "UNKNOWN_SOURCE"'''
        return self._guess.get('source') or 'UNKNOWN_SOURCE'

    @source.setter
    def source(self, value):
        self._guess['source'] = str(value) if value else ''

    @property
    def resolution(self):
        '''Resolution (e.g. "1080p") or "UNKNOWN_RESOLUTION"'''
        res = mediainfo.resolution(self._path)
        if res is None:
            res = self._guess.get('screen_size') or 'UNKNOWN_RESOLUTION'
        return res

    @resolution.setter
    def resolution(self, value):
        self._guess['screen_size'] = str(value) if value else ''

    @property
    def audio_format(self):
        '''Audio format or "UNKNOWN_AUDIO_FORMAT"'''
        af = mediainfo.audio_format(self._path)
        if af is None:
            af = self._guess.get('audio_codec') or 'UNKNOWN_AUDIO_FORMAT'
        return af

    @audio_format.setter
    def audio_format(self, value):
        self._guess['audio_codec'] = str(value) if value else ''

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
        self._guess['release_group'] = str(value) if value else 'NOGROUP'
