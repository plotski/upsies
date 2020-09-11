import asyncio
import collections
import re

from .. import errors
from ..tools import dbs, guessit
from . import _base, _common

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SearchDbJob(_base.JobBase):
    """
    Prompt user to select a specific search result from an internet database

    :param str db: Name of the database (see :mod:`tools.dbs` for a list)
    :param str content: Path or name of the release

    :raise ValueError: if `db` is unknown
    """

    @property
    def name(self):
        return self._db.label.lower()

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
        self._error_callbacks = []
        self._id_selected_callbacks = []

    def execute(self):
        self._search_thread = _SearchThread(
            search_coro=self._db.search,
            results_callback=self.handle_search_results,
            error_callback=self.handle_search_error,
            searching_callback=self.handle_searching_status,
        )
        self._search_thread.start()
        self._update_info_thread = _UpdateInfoThread(
            id=self._make_update_info_func('id'),
            summary=self._make_update_info_func('summary'),
            title_original=self._make_update_info_func('title_original'),
            title_english=self._make_update_info_func('title_english'),
            keywords=self._make_update_info_func('keywords'),
            cast=self._make_update_info_func('cast'),
            country=self._make_update_info_func('country'),
        )
        self._update_info_thread.start()

    def _make_update_info_func(self, key):
        return lambda value: self.update_info(key, value)

    def finish(self):
        if hasattr(self, '_search_thread'):
            self._search_thread.stop()
        if hasattr(self, '_update_info_thread'):
            self._update_info_thread.stop()
        super().finish()

    async def wait(self):
        await super().wait()
        if hasattr(self, '_update_info_thread'):
            await self._update_info_thread.join()
        if hasattr(self, '_search_thread'):
            await self._search_thread.join()

    def search(self, query):
        if not self.is_finished and hasattr(self, '_search_thread'):
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
            self._update_info_thread(results[0])
        else:
            self._update_info_thread(None)
        for cb in self._search_results_callbacks:
            cb(results)

    def on_error(self, callback):
        self._error_callbacks.append(callback)

    def handle_search_error(self, error):
        self.error(error, if_not_finished=True)
        for cb in self._error_callbacks:
            cb(error)

    def on_info_updated(self, callback):
        self._info_updated_callbacks.append(callback)

    def update_info(self, attr, value):
        for cb in self._info_updated_callbacks:
            cb(attr, value)

    def result_focused(self, result):
        self._update_info_thread(result)

    def on_id_selected(self, callback):
        self._id_selected_callbacks.append(callback)

    def id_selected(self, id=None):
        if not self.is_searching:
            if id is not None:
                self.send(str(id), if_not_finished=True)
            self.finish()
            for cb in self._id_selected_callbacks:
                cb(id, self._db)


class _SearchThread(_common.DaemonThread):
    def __init__(self, search_coro, results_callback, error_callback, searching_callback):
        self._search_coro = search_coro
        self._results_callback = results_callback
        self._searching_callback = searching_callback
        self._error_callback = error_callback
        self._loop = asyncio.new_event_loop()
        self._first_search = True
        self._query = ''
        self._search_task = None

    def stop(self):
        self._loop.stop()
        super().stop()

    @staticmethod
    def _normalize_query(query):
        # Case-insensitive, no leading/trailing white space and multiple white
        # space deduped
        return ' '.join(query.casefold().strip().split())

    def search(self, query):
        # Don't bother searching if nothing really changed
        if self._normalize_query(query) == self._normalize_query(self._query):
            return
        else:
            if self._search_task:
                self._search_task.cancel()
            self._query = query
            self.unblock()

    def work(self):
        # Retry searching until the search operation is not canceled
        while True:
            self._search_task = self._loop.create_task(self._delay_search())
            try:
                self._loop.run_until_complete(self._search_task)
            except asyncio.CancelledError:
                # Previous search was cancelled
                pass
            except RuntimeError:
                # The loop was stopped by stop()
                _log.debug('Search thread was stopped')
                break
            else:
                break

    async def _delay_search(self):
        # Wait for the user to stop typing
        await self._delay()
        self._results_callback(())
        self._searching_callback(True)
        title, kwargs = self._parse_query(self._query)
        try:
            results = await self._search_coro(title, **kwargs)
        except errors.RequestError as e:
            self._error_callback(e)
            results = []
        finally:
            self._searching_callback(False)
            if results:
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


class _UpdateInfoThread(_common.DaemonThread):
    def __init__(self, **targets):
        # `targets` maps names of SearchResult attributes to callbacks that get
        # the value of the corresponding SearchResult attribute.
        # Example: {"title" : lambda t: print(f'Title: {t}')}
        # NOTE: Values of SearchResult attributes may also be coroutine
        # functions that return the actual value.
        self._targets = targets
        self._result = None
        self._update_task = None
        self._loop = asyncio.new_event_loop()

    def stop(self):
        self._loop.stop()
        super().stop()

    def __call__(self, result):
        # Cancel previous update tasks
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
            _log.debug('Canceled previous update task: %r', self._update_task)
        self._result = result
        self.unblock()

        # Update plain, non-callable values immediately
        if result is not None:
            for attr, callback in self._targets.items():
                value = getattr(result, attr)
                if not callable(value):
                    callback(self._value_as_string(value))

    def work(self):
        if self._result is None:
            for callback in self._targets.values():
                callback('')
            return

        # Retry updating callable SearchResult attribute values until we are not
        # interupted by user selecting a different search result
        while True:
            tasks = self._make_update_tasks()
            if not tasks:
                break
            # Combine all callable values into a single task
            self._update_task = asyncio.gather(*tasks)
            try:
                self._loop.run_until_complete(self._update_task)
            except asyncio.CancelledError:
                _log.debug('Update info tasks were cancelled')
            except RuntimeError:
                # The loop was stopped by stop()
                _log.debug('Update info thread was stopped')
                break
            else:
                break

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
                    self._cache[cache_key] = self._value_as_string(await value_getter())
                except errors.RequestError as e:
                    self._cache[cache_key] = f'ERROR: {str(e)}'
                callback(self._cache[cache_key])
        return self._loop.create_task(coro(cache_key, value_getter, callback))

    @staticmethod
    def _value_as_string(value):
        if not isinstance(value, str) and isinstance(value, collections.abc.Iterable):
            return ', '.join(str(v) for v in value)
        else:
            return str(value)
