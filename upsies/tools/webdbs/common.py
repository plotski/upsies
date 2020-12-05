import asyncio
import re

from ...utils import guessit

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Query:
    """
    Search query for databases like IMDb

    :param str title: Name of the movie or TV series
    :param str type: "movie", "series" or "episode"
    :param year: Year of release
    :type year: str or int

    :raise ValueError: if an invalid argument is passed
    """

    def __init__(self, title, year=None, type=None):
        self.title = str(title)

        self.type = type if type is None else str(type).lower()
        if self.type is not None and self.type not in self._types:
            raise ValueError(f'Invalid type: {type}')

        self.year = year if year is None else str(year)
        if self.year is not None and not 1800 < int(self.year) < 2100:
            raise ValueError(f'Invalid year: {self.year}')

    _types = ('movie', 'series')
    _movie_types = ('movie', 'film')
    _series_types = ('series', 'tv', 'show', 'tvshow', 'episode', 'season')
    _kw_regex = {
        'year': r'year:(\d{4})',
        'type': rf'type:({"|".join(_movie_types + _series_types)})',
    }

    @classmethod
    def from_string(cls, query):
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
                    if kw == 'type' and value in cls._movie_types:
                        return 'type', 'movie'
                    elif kw == 'type' and value in cls._series_types:
                        return 'type', 'series'
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
        guess = guessit.guessit(path)
        kwargs = {'title': guess['title']}
        if guess.get('year'):
            kwargs['year'] = guess['year']
        if guess.get('type').casefold() == 'movie':
            kwargs['type'] = 'movie'
        elif guess.get('type').casefold() in ('season', 'episode', 'series'):
            kwargs['type'] = 'series'
        return cls(**kwargs)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            def normalize_title(t):
                return ' '.join(t.casefold().strip().split())

            return (
                normalize_title(self.title) == normalize_title(other.title)
                and self.year == other.year
                and self.type == other.type
            )
        else:
            return NotImplemented

    def __str__(self):
        parts = [self.title]
        if self.year:
            parts.append(f'year:{self.year}')
        if self.type:
            parts.append(f'type:{self.type}')
        return ' '.join(parts)

    def __repr__(self):
        kwargs = ', '.join(
            f'{k}={v!r}'
            for k, v in (('title', self.title),
                         ('year', self.year),
                         ('type', self.type))
            if v is not None
        )
        return f'{type(self).__name__}({kwargs})'


async def info(id, *corofuncs):
    """
    Combine return values from multiple coroutines into `dict`

    The keys of the returned dictionary are the names of the coroutine
    functions.

    :param str id: IMDb ID (starts with "tt")
    :param corofuncs: Info getters
    :type corofuncs: sequence of coroutine functions
    """
    aws = (corofunc(id) for corofunc in corofuncs)
    results = await asyncio.gather(*aws)
    # "The order of result values corresponds to the order of awaitables in `aws`."
    # https://docs.python.org/3/library/asyncio-task.html#running-tasks-concurrently
    return {corofunc.__name__: result
            for corofunc, result in zip(corofuncs, results)}


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
        if type not in ('movie', 'series', 'episode', ''):
            raise ValueError(f'Invalid type: {type!r}')
        self._info = {
            'id' : str(id),
            'url' : str(url),
            'type' : str(type),
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
