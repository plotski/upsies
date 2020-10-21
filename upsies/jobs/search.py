import asyncio
import collections
import re
from time import monotonic as time_monotonic

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

    def initialize(self, db, content_path):
        try:
            self._db = getattr(dbs, db)
        except AttributeError:
            raise ValueError(f'Invalid database name: {db}')
        self._query = dbs.Query.from_path(content_path)
        self._is_searching = False
        self._search_results_callbacks = []
        self._searching_status_callbacks = []
        self._info_updated_callbacks = []

        self._searcher = _Searcher(
            search_coro=self._db.search,
            results_callback=self.handle_search_results,
            searching_callback=self.handle_searching_status,
            error_callback=self.error,
        )
        self._info_updater = _InfoUpdater(
            id=self._make_update_info_func('id'),
            summary=self._make_update_info_func('summary'),
            title_original=self._make_update_info_func('title_original'),
            title_english=self._make_update_info_func('title_english'),
            keywords=self._make_update_info_func('keywords'),
            director=self._make_update_info_func('director'),
            cast=self._make_update_info_func('cast'),
            country=self._make_update_info_func('country'),
        )

    def _make_update_info_func(self, key):
        return lambda value: self.update_info(key, value)

    def execute(self):
        # Start initial search() *after* callbacks have been registered by UI
        self._searcher.search(self._query)

    async def wait(self):
        # Raise any exceptions
        await asyncio.gather(
            self._searcher.wait(),
            self._info_updater.wait(),
        )
        await super().wait()

    def search(self, query):
        if not self.is_finished:
            self._query = dbs.Query.from_string(query)
            self._searcher.search(self._query)

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
            self._info_updater.set_result(results[0])
        else:
            self._info_updater.set_result(None)
        for cb in self._search_results_callbacks:
            cb(results)

    def on_info_updated(self, callback):
        self._info_updated_callbacks.append(callback)

    def update_info(self, attr, value):
        for cb in self._info_updated_callbacks:
            cb(attr, value)

    def result_focused(self, result):
        self._info_updater.set_result(result)

    def id_selected(self, id=None):
        if not self.is_searching:
            if id is not None:
                self.send(str(id))
            self.finish()


class _Searcher:
    def __init__(self, search_coro, results_callback, searching_callback, error_callback):
        self._search_coro = search_coro
        self._results_callback = results_callback
        self._searching_callback = searching_callback
        self._error_callback = error_callback
        self._previous_search_time = 0
        self._search_future = None

    async def wait(self):
        if self._search_future:
            await self._search_future

    def search(self, query):
        """
        Schedule new query

        :param query: Query to make
        :type query: :class:`~tools.dbs.Query`
        """
        if self._search_future:
            self._search_future.cancel()
        self._search_future = asyncio.ensure_future(self._search(query))

    async def _search(self, query):
        self._results_callback(())
        self._searching_callback(True)
        await self._delay()
        results = ()
        try:
            results = await self._search_coro(
                title=query.title,
                year=query.year,
                type=query.type,
            )
        except errors.RequestError as e:
            self._error_callback(e)
        finally:
            self._searching_callback(False)
            self._results_callback(results)

    _min_seconds_between_searches = 1

    async def _delay(self):
        cur_time = time_monotonic()
        time_since_prev_search = cur_time - self._previous_search_time
        if time_since_prev_search <= self._min_seconds_between_searches:
            remaining_delay = self._min_seconds_between_searches - time_since_prev_search
            await asyncio.sleep(remaining_delay)
        self._previous_search_time = time_monotonic()


class _InfoUpdater:
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
        self._update_future = None

    async def wait(self):
        if self._update_future:
            await self._update_future

    def set_result(self, result):
        if self._update_future:
            self._update_future.cancel()
        self._result = result

        if not self._result:
            for callback in self._targets.values():
                callback('')
        else:
            self._update_future = asyncio.ensure_future(self._update())

        # Update plain, non-callable values immediately
        if result is not None:
            for attr, callback in self._targets.items():
                value = getattr(result, attr)
                if not callable(value):
                    callback(self._value_as_string(value))

    async def _update(self):
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
        return asyncio.ensure_future(coro(cache_key, value_getter, callback))

    @staticmethod
    def _value_as_string(value):
        if not isinstance(value, str) and isinstance(value, collections.abc.Iterable):
            return ', '.join(str(v) for v in value)
        else:
            return str(value)
