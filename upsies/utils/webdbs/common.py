"""
Classes and functions that are used by all :class:`~.base.WebDbApiBase`
subclasses
"""

import re

from .. import ReleaseType, release_info

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Query:
    """
    Search query for databases like IMDb

    :param str title: Name of the movie or TV series
    :param str type: :class:`~.utils.ReleaseType` enum or one of its value names
    :param year: Year of release
    :type year: str or int

    :raise ValueError: if an invalid argument is passed
    """

    def __init__(self, title, year=None, type=ReleaseType.unknown):
        self.type = ReleaseType(type)
        self.title = str(title)
        self.year = None if year is None else str(year)
        if self.year is not None and not 1800 < int(self.year) < 2100:
            raise ValueError(f'Invalid year: {self.year}')

    _types = {
        ReleaseType.movie: ('movie', 'film'),
        ReleaseType.season: ('season',),
        ReleaseType.episode: ('episode',),
        ReleaseType.series: ('series', 'tv', 'show', 'tvshow'),
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
                    if kw == 'type' and value in cls._types[ReleaseType.movie]:
                        return 'type', ReleaseType.movie
                    elif kw == 'type' and value in cls._types[ReleaseType.series]:
                        return 'type', ReleaseType.series
                    elif kw == 'type' and value in cls._types[ReleaseType.season]:
                        return 'type', ReleaseType.season
                    elif kw == 'type' and value in cls._types[ReleaseType.episode]:
                        return 'type', ReleaseType.episode
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

        `path` is passed to :class:`~.release_info.ReleaseInfo` to get the
        arguments for instantiation.
        """
        guess = release_info.ReleaseInfo(path)
        kwargs = {'title': guess['title']}
        if guess.get('year'):
            kwargs['year'] = guess['year']
        if guess.get('type'):
            kwargs['type'] = guess['type']
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
        if self.type is not ReleaseType.unknown:
            parts.append(f'type:{self.type}')
        return ' '.join(parts)

    def __repr__(self):
        kwargs = ', '.join(
            f'{k}={v!r}'
            for k, v in (('title', self.title),
                         ('year', self.year),
                         ('type', self.type))
            if v not in (None, ReleaseType.unknown)
        )
        return f'{type(self).__name__}({kwargs})'


class SearchResult:
    """
    Information about a search result

    Keyword arguments are available as attributes.

    `cast`, `countries`, `director`, `keywords`, `summary`, `title_english` and
    `title_original` may be coroutine functions that return the expected value.

    :param str director: Name of director
    :param cast: Short list of actor names
    :type cast: sequence of str
    :param str countries: List of country names of origin
    :param str id: ID for the relevant DB
    :param keywords: Short list of keywords, e.g. `["horror", "commedy"]`
    :type keywords: sequence of str
    :param summary: Short text that describes the movie or series
    :param str title: Title of the movie or series
    :param str title_english: English title of the movie or series
    :param str title_original: Original title of the movie or series
    :param str type: :class:`~.utils.ReleaseType` value
    :param str url: Web page of the search result
    :param str year: Release year; for series this should be the year of the
        first airing of the first episode of the first season
    """
    def __init__(self, *, id, type, url, year, cast=(), countries=(), director='',
                 keywords=(), summary='', title, title_english='',
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
            'director' : director,
            'keywords' : keywords,
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
