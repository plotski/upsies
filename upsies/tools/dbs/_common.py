import asyncio

import logging  # isort:skip
_log = logging.getLogger(__name__)


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
