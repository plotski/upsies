import asyncio
import collections
import re

from .. import errors
from ..tools import dbs
from ..utils import daemon, guessit
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SearchDbJob(JobBase):
    """
    Prompt user to select a specific search result from an internet database

    :param str db: Name of the database (see :mod:`tools.dbs` for a list)
    :param str content: Path or name of the release

    :raise ValueError: if `db` is unknown
    """

    @property
    def name(self):
        return f'{self._db.label.lower()}-id'

    @property
    def label(self):
        return f'{self._db.label} ID'

    @property
    def query(self):
        return self._query

    @staticmethod
    def _make_query_from_path(content_path):
        guess = guessit.guessit(content_path)
        query = [guess['title']]
        if guess.get('year'):
            query.append('year:' + guess['year'])
        if guess.get('type') == 'movie':
            query.append('type:movie')
        elif guess.get('type') in ('season', 'episode', 'series'):
            query.append('type:series')
        return ' '.join(query)

    def initialize(self, db, content_path):
        try:
            self._db = getattr(dbs, db)
        except AttributeError:
            raise ValueError(f'Invalid database name: {db}')
        self._query = self._make_query_from_path(content_path)
        self._is_searching = False
        self._search_results_callbacks = []
        self._searching_status_callbacks = []
        self._info_updated_callbacks = []

        # Set self._update_info_thread before self._search_thread because the
        # search thread will call self._update_info_thread.set_result() as soon
        # as it gets results, potentially before _UpdateInfoThread() returns.
        self._update_info_thread = _UpdateInfoThread(
            id=self._make_update_info_func('id'),
            summary=self._make_update_info_func('summary'),
            title_original=self._make_update_info_func('title_original'),
            title_english=self._make_update_info_func('title_english'),
            keywords=self._make_update_info_func('keywords'),
            director=self._make_update_info_func('director'),
            cast=self._make_update_info_func('cast'),
            country=self._make_update_info_func('country'),
        )
        self._search_thread = _SearchThread(
            query=self._query,
            search_coro=self._db.search,
            results_callback=self.handle_search_results,
            error_callback=self.error,
            searching_callback=self.handle_searching_status,
        )

    def _make_update_info_func(self, key):
        return lambda value: self.update_info(key, value)

    def execute(self):
        self._update_info_thread.start()
        self._search_thread.start()

    def finish(self):
        self._update_info_thread.stop()
        self._search_thread.stop()
        super().finish()

    async def wait(self):
        # Raise any exceptions from the threads
        await asyncio.gather(
            self._update_info_thread.join(),
            self._search_thread.join(),
        )
        await super().wait()

    def search(self, query):
        if not self.is_finished:
            self._search_thread.search(query)

    def on_searching_status(self, callback):
        self._searching_status_callbacks.append(callback)

    def handle_searching_status(self, is_searching):
        self._is_searching = bool(is_searching)
        for cb in self._searching_status_callbacks:
            cb(is_searching)

    @property
    def is_searching(self):
        return self._is_searching

    def on_search_results(self, callback):
        self._search_results_callbacks.append(callback)

    def handle_search_results(self, results):
        if results:
            self._update_info_thread.set_result(results[0])
        else:
            self._update_info_thread.set_result(None)
        for cb in self._search_results_callbacks:
            cb(results)

    def on_info_updated(self, callback):
        self._info_updated_callbacks.append(callback)

    def update_info(self, attr, value):
        for cb in self._info_updated_callbacks:
            cb(attr, value)

    def result_focused(self, result):
        self._update_info_thread.set_result(result)

    def id_selected(self, id=None):
        if not self.is_searching:
            if id is not None:
                self.send(str(id))
            self.finish()


class _SearchThread(daemon.DaemonThread):
    def __init__(self, search_coro, results_callback, error_callback, searching_callback,
                 query=''):
        super().__init__()
        self._search_coro = search_coro
        self._results_callback = results_callback
        self._searching_callback = searching_callback
        self._error_callback = error_callback
        self._first_search = True
        self.query = query

    @property
    def query(self):
        return getattr(self, '_query', '')

    @query.setter
    def query(self, query):
        # Normalize query:
        #   - Case-insensitive
        #   - Remove leading/trailing white space
        #   - Deduplicate white space
        self._query = ' '.join(query.casefold().strip().split())

    def search(self, query):
        """
        Schedule new query

        :param str query: Query to make; "year:YYYY", "type:series" and
            "type:movie" are interpreted to reduce the number of search results
        """
        self.query = query
        self.cancel_work()
        self.unblock()

    async def work(self):
        # Wait for the user to stop typing
        await self._delay()
        self._results_callback(())
        self._searching_callback(True)
        title, kwargs = self._parse_query(self.query)
        results = ()
        try:
            results = await self._search_coro(title, **kwargs)
        except errors.RequestError as e:
            self._error_callback(e)
        finally:
            self._searching_callback(False)
            self._results_callback(results)

    _movie_types = ('movie', 'film')
    _series_types = ('series', 'tv', 'show', 'episode', 'season')
    _kwargs_regex = {
        'year': r'year:(\d{4})',
        'type': rf'type:({"|".join(_movie_types + _series_types)})',
    }

    @classmethod
    def _parse_query(cls, query):

        def get_kwarg(string):
            for kw, regex in cls._kwargs_regex.items():
                match = re.search(f'^{regex}$', part)
                if match:
                    value = match.group(1)
                    if kw == 'type' and value in cls._movie_types:
                        return kw, 'movie'
                    elif kw == 'type' and value in cls._series_types:
                        return kw, 'series'
                    elif kw == 'year':
                        return kw, value
            return None, None

        kwargs = {}
        query_parts = []
        for part in query.split():
            kw, value = get_kwarg(part)
            if (kw, value) != (None, None):
                kwargs[kw] = value
            else:
                query_parts.append(part)

        return ' '.join(query_parts), kwargs

    _seconds_between_searches = 1

    async def _delay(self):
        # Do not delay if this is the first search
        if self._first_search:
            self._first_search = False
        else:
            try:
                await asyncio.sleep(self._seconds_between_searches)
            except asyncio.CancelledError:
                raise


class _UpdateInfoThread(daemon.DaemonThread):
    def __init__(self, **targets):
        super().__init__()
        # `targets` maps names of SearchResult attributes to callbacks that get
        # the value of the corresponding SearchResult attribute.
        # Example: {"title" : lambda t: print(f'Title: {t}')}
        # NOTE: Values of SearchResult attributes may also be coroutine
        #       functions that return the actual value.
        self._targets = targets
        # SearchResult instance or None
        self._result = None

    def set_result(self, result):
        self._result = result
        self.cancel_work()
        self.unblock()

        # Update plain, non-callable values immediately
        if result is not None:
            for attr, callback in self._targets.items():
                value = getattr(result, attr)
                if not callable(value):
                    callback(self._value_as_string(value))

    async def work(self):
        if self._result is None:
            for callback in self._targets.values():
                callback('')
        else:
            tasks = self._make_update_tasks()
            await asyncio.gather(*tasks)

    def _make_update_tasks(self):
        tasks = []
        for attr, callback in self._targets.items():
            value = getattr(self._result, attr)
            if callable(value):
                tasks.append(self._make_update_task(
                    cache_key=(self._result.id, attr),
                    value_getter=value,
                    callback=callback,
                ))
        return tasks

    _cache = {}
    _delay_between_updates = 0.5

    def _make_update_task(self, cache_key, value_getter, callback):
        async def coro(cache_key, value_getter, callback):
            cached_value = self._cache.get(cache_key, None)
            if cached_value is not None:
                callback(cached_value)
            else:
                callback('Loading...')
                await asyncio.sleep(self._delay_between_updates)
                try:
                    value = self._value_as_string(await value_getter())
                except errors.RequestError as e:
                    callback(f'ERROR: {str(e)}')
                else:
                    self._cache[cache_key] = value
                    callback(value)
        return self._loop.create_task(coro(cache_key, value_getter, callback))

    @staticmethod
    def _value_as_string(value):
        if not isinstance(value, str) and isinstance(value, collections.abc.Iterable):
            return ', '.join(str(v) for v in value)
        else:
            return str(value)
