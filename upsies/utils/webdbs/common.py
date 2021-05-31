"""
Classes and functions that are used by all :class:`~.base.WebDbApiBase`
subclasses
"""

import re

from .. import release
from ..types import ReleaseType

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Query:
    """
    Search query for databases like IMDb

    :param str title: Name of the movie or TV series
    :param type: :class:`~.types.ReleaseType` enum or one of its value names
    :param year: Year of release
    :type year: str or int
    :param str id: Known ID for a specific DB

    :raise ValueError: if an invalid argument is passed
    """

    @staticmethod
    def _normalize_title(title):
        return ' '.join(title.casefold().strip().split())

    _kwarg_defaults = {
        'year': None,
        'type': ReleaseType.unknown,
        'id': None,
    }

    def __init__(self, title='', **kwargs):
        self.title = title
        self.type = kwargs.get('type', self._kwarg_defaults['type'])
        self.year = kwargs.get('year', self._kwarg_defaults['year'])
        self.id = kwargs.get('id', self._kwarg_defaults['id'])
        self._title_normalized = self._normalize_title(self.title)
        self._kwargs_order = tuple(kwargs)

    @property
    def type(self):
        """:class:`~.types.ReleaseType` value"""
        return self._type

    @type.setter
    def type(self, type):
        self._type = ReleaseType(type)

    @property
    def title(self):
        """Name of the movie or TV series"""
        return self._title

    @title.setter
    def title(self, title):
        self._title = str(title)

    @property
    def title_normalized(self):
        """Same as :attr:`title` but in stripped lower case with deduplicated spaces"""
        return self._title_normalized

    @property
    def year(self):
        """Year of release"""
        return self._year

    @year.setter
    def year(self, year):
        if year is None:
            self._year = None
        else:
            try:
                year_int = int(year)
            except (TypeError, ValueError):
                raise ValueError(f'Invalid year: {year}')
            else:
                if not 1800 < year_int < 2100:
                    raise ValueError(f'Invalid year: {year}')
                else:
                    self._year = str(year_int)

    @property
    def id(self):
        """Known ID for a specific DB"""
        return self._id

    @id.setter
    def id(self, id):
        self._id = None if id is None else str(id)

    _types = {
        ReleaseType.movie: ('movie', 'film'),
        ReleaseType.season: ('season', 'series', 'tv', 'show', 'tvshow'),
        ReleaseType.episode: ('episode',),
    }
    _known_types = tuple(v for types in _types.values() for v in types)
    _kw_regex = {
        'year': r'year:(\d{4})',
        'type': rf'type:({"|".join(_known_types)})',
        'id': r'id:(\S+)',
    }

    @classmethod
    def from_string(cls, query):
        """
        Create instance from string

        The returned :class:`Query` is case-insensitive and has any superfluous
        whitespace removed.

        Keyword arguments are extracted by looking for ``"year:YEAR"``,
        ``"type:TYPE"`` and ``"id:ID"`` in `query` where ``YEAR`` is a
        four-digit number, ``TYPE`` is something like "movie", "film", "tv", etc
        and ``ID`` is a known ID for the DB this query is meant for.
        """
        def get_kwarg(string):
            for kw, regex in cls._kw_regex.items():
                match = re.search(f'^{regex}$', part)
                if match:
                    value = match.group(1)
                    if kw == 'type' and value in cls._types[ReleaseType.movie]:
                        return 'type', ReleaseType.movie
                    elif kw == 'type' and value in cls._types[ReleaseType.season]:
                        return 'type', ReleaseType.season
                    elif kw == 'type' and value in cls._types[ReleaseType.episode]:
                        return 'type', ReleaseType.episode
                    elif kw == 'year':
                        return 'year', value
                    elif kw == 'id':
                        return 'id', value
            return None, None

        # Extract "key:value" pairs (e.g. "year:2015")
        title = []
        kwargs = {}
        for part in str(query).strip().split():
            kw, value = get_kwarg(part)
            if (kw, value) != (None, None):
                kwargs[kw] = value
            else:
                title.append(part)
        if title:
            kwargs['title'] = ' '.join(title)
        return cls(**kwargs)

    @classmethod
    def from_path(cls, path):
        """
        Create instance from file or directory name

        `path` is passed to :class:`~.release.ReleaseInfo` to get the
        arguments for instantiation.
        """
        info = release.ReleaseInfo(path)
        kwargs = {'title': info['title']}
        if info.get('year'):
            kwargs['year'] = info['year']
        if info.get('type'):
            kwargs['type'] = info['type']
        return cls(**kwargs)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self.title_normalized == other.title_normalized
                and self.year == other.year
                and self.type is other.type
                and self.id == other.id
            )
        else:
            return NotImplemented

    def __str__(self):
        if self.id:
            return f'id:{self.id}'
        else:
            parts = [self.title]
            for attr in self._kwargs_order:
                value = getattr(self, attr)
                if value:
                    parts.append(f'{attr}:{value}')
            return ' '.join(parts)

    def __repr__(self):
        kwargs = ', '.join(
            f'{k}={v!r}'
            for k, v in (('title', self.title),
                         ('year', self.year),
                         ('type', self.type),
                         ('id', self.id))
            if v
        )
        return f'{type(self).__name__}({kwargs})'


class SearchResult:
    """
    Information about a search result

    Keyword arguments are available as attributes.

    `cast`, `countries`, `directors`, `genres`, `summary`, `title_english` and
    `title_original` may be coroutine functions that return the expected value.

    :param str directors: Sequence of directors
    :param cast: Short list of actor names
    :type cast: sequence of str
    :param str countries: List of country names of origin
    :param str id: ID for the relevant DB
    :param genres: Short list of genres, e.g. `["horror", "commedy"]`
    :type genres: sequence of str
    :param summary: Short text that describes the movie or series
    :param str title: Title of the movie or series
    :param str title_english: English title of the movie or series
    :param str title_original: Original title of the movie or series
    :param str type: :class:`~.types.ReleaseType` value
    :param str url: Web page of the search result
    :param str year: Release year; for series this should be the year of the
        first airing of the first episode of the first season
    """
    def __init__(self, *, id, type, url, year, cast=(), countries=(), directors='',
                 genres=(), summary='', title, title_english='',
                 title_original=''):
        self._info = {
            'id' : id,
            'title' : str(title),
            'type' : ReleaseType(type),
            'url' : str(url),
            'year' : str(year),
            # These may be coroutine functions
            'cast' : cast,
            'countries' : countries,
            'directors' : directors,
            'genres' : genres,
            'summary' : summary,
            'title_english' : title_english,
            'title_original' : title_original,
        }

    def __getattr__(self, name):
        try:
            return self._info[name]
        except KeyError:
            raise AttributeError(name)

    def __repr__(self):
        kwargs = ', '.join(f'{k}={v!r}' for k, v in self._info.items())
        return f'{type(self).__name__}({kwargs})'


class Person(str):
    """:class:`str` subclass with an `url` attribute"""

    def __new__(cls, name, url=''):
        obj = super().__new__(cls, name)
        obj.url = url
        return obj
