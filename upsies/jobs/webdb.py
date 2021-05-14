"""
Query online databases like IMDb
"""

import asyncio
import collections
from time import monotonic as time_monotonic

from .. import errors
from ..utils import fs, webdbs
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class WebDbSearchJob(JobBase):
    """
    Ask user to select a specific search result from an internet database

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``search_results``
            Emitted after new search results are available. Registered callbacks
            get a sequence of :class:`~.utils.webdbs.common.SearchResult`
            instances as a positional argument.

        ``searching_status``
            Emitted when a new search is started and when new results are
            available. Registered callbacks get `True` for "search started" or
            `False` for "search ended" as a positional argument.

        ``info_updating``
            Emitted when an attempt to fetch additional information is made.
            Registered callbacks get the name of an attribute of a
            :class:`~.utils.webdbs.common.SearchResult` object that returns a
            coroutine function as a positional argument.

        ``info_updated``
            Emitted when additional information is available. Registered
            callbacks are called for each piece of information and get ``key``
            and ``value`` as positional arguments. ``key`` is an attribute of a
            :class:`~.utils.webdbs.common.SearchResult` object that returns a
            coroutine function. ``value`` is the return value of that coroutine
            function.
    """

    @property
    def name(self):
        return f'{self._db.name}-id'

    @property
    def label(self):
        return f'{self._db.label} ID'

    @property
    def cache_id(self):
        """Final segment of `content_path` and database :attr:`~.WebDbApiBase.name`"""
        return fs.basename(self._content_path)

    @property
    def query(self):
        """:class:`~.webdbs.common.Query` instance"""
        return self._query

    def initialize(self, *, db, content_path):
        """
        Set internal state

        :param WebDbApiBase db: Return value of :func:`.utils.webdbs.webdb`
        :param str content_path: Path or name of the release (doesn't have to
            exist)
        """
        assert isinstance(db, webdbs.WebDbApiBase), f'Not a WebDbApiBase: {db!r}'
        self._db = db
        self._content_path = content_path
        self._query = self._db.sanitize_query(webdbs.Query.from_path(content_path))
        self._is_searching = False

        self.signal.add('search_results')
        self.signal.add('searching_status')
        self.signal.add('info_updating')
        self.signal.add('info_updated')

        self._searcher = _Searcher(
            search_coro=self._db.search,
            results_callback=self._handle_search_results,
            searching_callback=self._handle_searching_status,
            error_callback=self.warn,
            exception_callback=self.exception,
        )
        self._info_updater = _InfoUpdater(
            error_callback=self.warn,
            exception_callback=self.exception,
            targets={
                'id': self._make_update_info_func('id'),
                'summary': self._make_update_info_func('summary'),
                'title_original': self._make_update_info_func('title_original'),
                'title_english': self._make_update_info_func('title_english'),
                'genres': self._make_update_info_func('genres'),
                'directors': self._make_update_info_func('directors'),
                'cast': self._make_update_info_func('cast'),
                'countries': self._make_update_info_func('countries'),
            },
        )

    def _make_update_info_func(self, key):
        return lambda value: self._update_info(key, value)

    def _update_info(self, attr, value):
        if value is Ellipsis:
            self.signal.emit('info_updating', attr)
        else:
            self.signal.emit('info_updated', attr, value)

    def execute(self):
        """Search for initial query"""
        # It is important NOT to do this in initialize() because the window
        # between initialize() and execute() is used to register callbacks.
        self.search(self._query)

    async def wait(self):
        """Wait for any running internal coroutines"""
        # Raise any exceptions and avoid warnings about unawaited tasks
        await asyncio.gather(
            self._searcher.wait(),
            self._info_updater.wait(),
        )
        await super().wait()

    def finish(self):
        """Cancel any running internal coroutines and finish"""
        self._searcher.cancel()
        self._info_updater.cancel()
        super().finish()

    def search(self, query):
        """Make a new search request after cancelling any currently ongoing request"""
        if not self.is_finished:
            self._query = self._db.sanitize_query(webdbs.Query.from_string(query))
            self._searcher.search(self._query)
            self.clear_warnings()

    def _handle_searching_status(self, is_searching):
        self._is_searching = bool(is_searching)
        self.signal.emit('searching_status', self._is_searching)

    @property
    def is_searching(self):
        """Whether a search request is currently being made"""
        return self._is_searching

    def _handle_search_results(self, results):
        if results:
            self._info_updater.set_result(results[0])
        else:
            self._info_updater.set_result(None)
        self.signal.emit('search_results', results)

    def result_focused(self, result):
        """
        Must be called by the UI when the user focuses a different search result

        :param SearchResult result: Focused search result or `None` if there are
            no results
        """
        self._info_updater.set_result(result)

    def result_selected(self, result):
        """
        Must be called by the UI when the user accepts a search result

        :param SearchResult result: Focused search result or `None` if there are
            no results of if the user refused every result
        """
        if not self.is_searching:
            if result is not None:
                self.send(str(result.id))
            self.finish()


class _Searcher:
    def __init__(self, search_coro, results_callback, searching_callback,
                 error_callback, exception_callback):
        self._search_coro = search_coro
        self._results_callback = results_callback
        self._searching_callback = searching_callback
        self._error_callback = error_callback
        self._exception_callback = exception_callback
        self._previous_search_time = 0
        self._search_task = None

    async def wait(self):
        if self._search_task:
            try:
                await self._search_task
            except asyncio.CancelledError:
                pass

    def cancel(self):
        if self._search_task:
            self._search_task.cancel()

    def _handle_search_task(self, task):
        try:
            if task.exception():
                self._exception_callback(task.exception())
        except asyncio.CancelledError:
            pass

    def search(self, query):
        """
        Schedule new query

        :param query: Query to make
        :type query: :class:`~.utils.webdbs.Query`
        """
        if self._search_task:
            self._search_task.cancel()
            self._search_task = None
        self._search_task = asyncio.ensure_future(self._search(query))
        self._search_task.add_done_callback(self._handle_search_task)

    async def _search(self, query):
        self._results_callback(())
        self._searching_callback(True)
        await self._delay()
        results = ()
        try:
            results = await self._search_coro(query)
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
    def __init__(self, targets, error_callback, exception_callback):
        super().__init__()
        # `targets` maps names of SearchResult attributes to callbacks that get
        # the value of each attribute. For example, {"title": handle_title}
        # means: For each search_result, call handle_title(search_result.title).
        # Values of SearchResult attributes may also be coroutine functions that
        # return the actual value. In that case, call
        # handle_title(await search_result.title()).
        self._targets = targets
        self._error_callback = error_callback
        self._exception_callback = exception_callback
        # SearchResult instance or None
        self._result = None
        self._update_task = None

    async def wait(self):
        if self._update_task:
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

    def cancel(self):
        if self._update_task:
            self._update_task.cancel()

    def _handle_update_task(self, task):
        try:
            if task.exception():
                self._exception_callback(task.exception())
        except asyncio.CancelledError:
            pass

    def set_result(self, result):
        self.cancel()
        self._result = result

        if not self._result:
            for callback in self._targets.values():
                callback('')
        else:
            # Schedule calls of SearchResult attributes that are coroutine
            # functions
            self._update_task = asyncio.ensure_future(self._update())
            self._update_task.add_done_callback(self._handle_update_task)

            # Update plain, non-callable values immediately
            if result is not None:
                for attr, callback in self._targets.items():
                    value = getattr(result, attr)
                    if not callable(value):
                        callback(self._value_as_string(value))

    async def _update(self):
        tasks = []
        for attr, callback in self._targets.items():
            value = getattr(self._result, attr)
            if callable(value):
                tasks.append(self._call_callback(
                    callback=callback,
                    value_getter=value,
                    cache_key=(self._result.id, attr),
                ))
        await asyncio.gather(*tasks)

    _cache = {}
    _delay_between_updates = 0.5

    async def _call_callback(self, callback, value_getter, cache_key):
        cached_value = self._cache.get(cache_key, None)
        if cached_value is not None:
            callback(cached_value)
        else:
            # Indicate "Loading..." status
            callback(Ellipsis)
            await asyncio.sleep(self._delay_between_updates)
            try:
                value = await value_getter()
            except errors.RequestError as e:
                callback('')
                self._error_callback(e)
            else:
                value_str = self._value_as_string(value)
                self._cache[cache_key] = value_str
                callback(value_str)

    @staticmethod
    def _value_as_string(value):
        if not isinstance(value, str) and isinstance(value, collections.abc.Iterable):
            return ', '.join(str(v) for v in value)
        else:
            return str(value)
