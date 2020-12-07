import enum
import re

from ...utils import guessit

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Type(enum.Enum):
    """Movie, series, season, episode or unknown"""

    movie = 'movie'
    series = 'series'
    season = 'season'
    episode = 'episode'
    unknown = 'unknown'

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f'{type(self).__name__}.{self.value}'


class Query:
    """
    Search query for databases like IMDb

    :param str title: Name of the movie or TV series
    :param str type: "movie", "series" or "episode"
    :param year: Year of release
    :type year: str or int

    :raise ValueError: if an invalid argument is passed
    """

    def __init__(self, title, year=None, type=Type.unknown):
        if not isinstance(type, Type):
            raise ValueError(f'Invalid type: {type!r}')
        self.type = type
        self.title = str(title)
        self.year = None if year is None else str(year)
        if self.year is not None and not 1800 < int(self.year) < 2100:
            raise ValueError(f'Invalid year: {self.year}')

    _types = {
        Type.movie: ('movie', 'film'),
        Type.season: ('season',),
        Type.episode: ('episode',),
        Type.series: ('series', 'tv', 'show', 'tvshow'),
    }
    _known_types = tuple(v for types in _types.values() for v in types)
    _kw_regex = {
        'year': r'year:(\d{4})',
        'type': rf'type:({"|".join(_known_types)})',
    }

    @classmethod
    def from_string(cls, query):
        """
        Create instance from string

        The returned :class:`Query` is case-insensitive and has any superfluous
        whitespace removed.

        Keyword arguments are extracted by looking for ``"year:YEAR"`` and
        ``"type:TYPE"`` in `query` where ``YEAR`` is a four-digit number and
        ``TYPE`` is something like "movie", "film", "tv", etc.
        """
        # Normalize query:
        #   - Case-insensitive
        #   - Remove leading/trailing white space
        #   - Deduplicate white space
        query = ' '.join(str(query).strip().split())

        def get_kwarg(string):
            for kw, regex in cls._kw_regex.items():
                match = re.search(f'^{regex}$', part)
                if match:
                    value = match.group(1)
                    if kw == 'type' and value in cls._types[Type.movie]:
                        return 'type', Type.movie
                    elif kw == 'type' and value in cls._types[Type.season]:
                        return 'type', Type.season
                    elif kw == 'type' and value in cls._types[Type.episode]:
                        return 'type', Type.episode
                    elif kw == 'type' and value in cls._types[Type.series]:
                        return 'type', Type.series
                    elif kw == 'year':
                        return 'year', value
            return None, None

        # Extract "key:value" pairs (e.g. "year:2015")
        title = []
        kwargs = {}
        for part in query.split():
            kw, value = get_kwarg(part)
            if (kw, value) != (None, None):
                kwargs[kw] = value
            else:
                title.append(part)

        return cls(title=' '.join(title), **kwargs)

    @classmethod
    def from_path(cls, path):
        """
        Create instance from file or directory name

        `path` is passed to :func:`~.guessit.guessit` to get the arguments for
        instantiation.
        """
        guess = guessit.guessit(path)
        kwargs = {'title': guess['title']}

        if guess.get('year'):
            kwargs['year'] = guess['year']

        if guess.get('type').casefold() == 'movie':
            kwargs['type'] = Type.movie
        elif guess.get('type').casefold() == 'season':
            kwargs['type'] = Type.season
        elif guess.get('type').casefold() == 'episode':
            kwargs['type'] = Type.episode

        return cls(**kwargs)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            def normalize_title(t):
                return ' '.join(t.casefold().strip().split())

            return (
                normalize_title(self.title) == normalize_title(other.title)
                and self.year == other.year
                and self.type is other.type
            )
        else:
            return NotImplemented

    def __str__(self):
        parts = [self.title]
        if self.year:
            parts.append(f'year:{self.year}')
        if self.type is not Type.unknown:
            parts.append(f'type:{self.type}')
        return ' '.join(parts)

    def __repr__(self):
        kwargs = ', '.join(
            f'{k}={v!r}'
            for k, v in (('title', self.title),
                         ('year', self.year),
                         ('type', self.type))
            if v not in (None, Type.unknown)
        )
        return f'{type(self).__name__}({kwargs})'


class SearchResult:
    """
    Information about a search result

    :param str id: ID for the relevant DB (e.g. IMDb IDs start with "tt")
    :param str type: "movie", "series", "episode" or "" (unknown)
    :param str title: Title of the movie or series
    :param str year: Release year; for series this should be the year of the
        first airing of the first episode of the first season
    :param keywords: Short list of keywords, e.g. `["horror", "commedy"]`
    :type keywords: sequence of str
    :param str director: Name of director
    :param cast: Short list of actor names
    :type cast: sequence of str
    :param summary: Short text that describes the movie or series
    :type summary: str or coroutine function

    `summary`, `keywords`, `cast`, `title_original` and `title_english` can also
    be coroutine functions that return the expected value.
    """
    def __init__(self, *, id, url, type, year, title, title_original='',
                 title_english='', keywords=(), director='', cast=(), summary='',
                 country=''):
        if not isinstance(type, Type):
            raise ValueError(f'Invalid type: {type!r}')
        self._info = {
            'id' : str(id),
            'url' : str(url),
            'type' : type,
            'year' : str(year),
            'title' : str(title),

            # These may be coroutine functions
            'title_original' : title_original,
            'title_english' : title_english,
            'keywords' : keywords,
            'director' : director,
            'cast' : cast,
            'summary' : summary,
            'country' : country,
        }

    def __getattr__(self, name):
        try:
            return self._info[name]
        except KeyError:
            raise AttributeError(name)

    def __repr__(self):
        kwargs = ', '.join(f'{k}={v!r}' for k, v in self._info.items())
        return f'{type(self).__name__}({kwargs})'
