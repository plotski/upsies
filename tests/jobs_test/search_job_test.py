import asyncio
import time
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs import search


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


def test_name(tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert sj.name == 'imdb-id'


def test_label(tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert sj.label == 'IMDb ID'


@patch('upsies.jobs.search.SearchDbJob._make_query_from_path')
def test_query(make_query_mock, tmp_path):
    make_query_mock.return_value = 'query string'
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert sj.query == 'query string'


@patch('upsies.utils.guessit.guessit')
@pytest.mark.parametrize(
    argnames=('guess', 'exp_query'),
    argvalues=(
        ({'title': 'The Foo'}, 'The Foo'),
        ({'title': 'The Foo', 'year': '1234'}, 'The Foo year:1234'),
        ({'title': 'The Foo', 'year': '1234', 'type': 'movie'}, 'The Foo year:1234 type:movie'),
        ({'title': 'The Foo', 'year': '1234', 'type': 'series'}, 'The Foo year:1234 type:series'),
        ({'title': 'The Foo', 'year': '1234', 'type': 'episode'}, 'The Foo year:1234 type:series'),
        ({'title': 'The Foo', 'type': 'movie'}, 'The Foo type:movie'),
        ({'title': 'The Foo', 'type': 'series'}, 'The Foo type:series'),
        ({'title': 'The Foo', 'type': 'episode'}, 'The Foo type:series'),
    ),
    ids=lambda val: ','.join(f'{k}={v}' for k, v in val.items()) if isinstance(val, dict) else val,
)
def test_make_query_from_path_with_year(guessit_mock, tmp_path, guess, exp_query):
    guessit_mock.return_value = guess
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert sj.query == exp_query


def test_unknown_db(tmp_path):
    with pytest.raises(ValueError, match=r'^Invalid database name: foo$'):
        search.SearchDbJob(
            homedir=tmp_path,
            ignore_cache=False,
            db='foo',
            content_path='path/to/foo',
        )


@patch('upsies.jobs.search._UpdateInfoThread')
@patch('upsies.jobs.search._SearchThread')
def test_initialize_creates_search_thread(SearchThread_mock, UpdateInfoThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert sj._search_thread is SearchThread_mock.return_value
    assert SearchThread_mock.call_args_list == [call(
        query='foo type:movie',
        search_coro=search.dbs.imdb.search,
        results_callback=sj.handle_search_results,
        error_callback=sj.error,
        searching_callback=sj.handle_searching_status,
    )]
    assert SearchThread_mock.return_value.start.call_args_list == []

@patch('upsies.jobs.search.SearchDbJob._make_update_info_func')
@patch('upsies.jobs.search._UpdateInfoThread')
@patch('upsies.jobs.search._SearchThread')
def test_initialize_creates_update_info_thread(SearchThread_mock,
                                               UpdateInfoThread_mock,
                                               make_update_info_func_mock,
                                               tmp_path):
    make_update_info_func_mock.side_effect = (
        'id func',
        'summary func',
        'title_original func',
        'title_english func',
        'keywords func',
        'cast func',
        'country func',
    )
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert sj._update_info_thread is UpdateInfoThread_mock.return_value
    assert UpdateInfoThread_mock.call_args_list == [call(
        id='id func',
        summary='summary func',
        title_original='title_original func',
        title_english='title_english func',
        keywords='keywords func',
        cast='cast func',
        country='country func',
    )]
    assert sj._update_info_thread.start.call_args_list == []
    assert make_update_info_func_mock.call_args_list == [
        call('id'),
        call('summary'),
        call('title_original'),
        call('title_english'),
        call('keywords'),
        call('cast'),
        call('country'),
    ]


@patch('upsies.jobs.search._UpdateInfoThread')
@patch('upsies.jobs.search._SearchThread')
def test_execute_starts_search_thread(SearchThread_mock, UpdateInfoThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert sj._search_thread.start.call_args_list == []
    sj.execute()
    assert SearchThread_mock.return_value.start.call_args_list == [call()]

@patch('upsies.jobs.search._UpdateInfoThread')
@patch('upsies.jobs.search._SearchThread')
def test_execute_starts_update_info_thread(SearchThread_mock, UpdateInfoThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert sj._update_info_thread.call_args_list == []
    sj.execute()
    assert sj._update_info_thread.start.call_args_list == [call()]


@patch('upsies.jobs.search.SearchDbJob.update_info')
def test_make_update_info_func(update_info_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    func = sj._make_update_info_func('key')
    func('value 1')
    assert sj.update_info.call_args_list == [call('key', 'value 1')]
    func('value 2')
    assert sj.update_info.call_args_list == [call('key', 'value 1'), call('key', 'value 2')]


@patch('upsies.jobs.search._UpdateInfoThread')
@patch('upsies.jobs.search._SearchThread')
def test_finish_before_execution(SearchThread_mock, UpdateInfoThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert not sj.is_finished
    sj.finish()
    assert sj.is_finished
    assert SearchThread_mock.return_value.stop.call_args_list == []
    assert UpdateInfoThread_mock.return_value.stop.call_args_list == []

@patch('upsies.jobs.search._UpdateInfoThread')
@patch('upsies.jobs.search._SearchThread')
def test_finish_after_execution(SearchThread_mock, UpdateInfoThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert not sj.is_finished
    sj.execute()
    assert not sj.is_finished
    sj.finish()
    assert sj.is_finished
    assert SearchThread_mock.return_value.stop.call_args_list == [call()]
    assert UpdateInfoThread_mock.return_value.stop.call_args_list == [call()]


@patch('upsies.jobs.search._UpdateInfoThread')
@patch('upsies.jobs.search._SearchThread')
def test_wait_before_execution(SearchThread_mock, UpdateInfoThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    SearchThread_mock.return_value.join = AsyncMock()
    UpdateInfoThread_mock.return_value.join = AsyncMock()
    asyncio.get_event_loop().call_soon(sj.finish)
    asyncio.get_event_loop().run_until_complete(sj.wait())
    assert sj.is_finished
    assert SearchThread_mock.return_value.join.call_args_list == []
    assert UpdateInfoThread_mock.return_value.join.call_args_list == []

@patch('upsies.jobs.search._UpdateInfoThread')
@patch('upsies.jobs.search._SearchThread')
def test_wait_after_execution(SearchThread_mock, UpdateInfoThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    SearchThread_mock.return_value.join = AsyncMock()
    UpdateInfoThread_mock.return_value.join = AsyncMock()
    sj.execute()
    asyncio.get_event_loop().call_soon(sj.finish)
    asyncio.get_event_loop().run_until_complete(sj.wait())
    assert sj.is_finished
    assert SearchThread_mock.return_value.join.call_args_list == [call()]
    assert UpdateInfoThread_mock.return_value.join.call_args_list == [call()]


@patch('upsies.jobs.search._SearchThread')
def test_search_before_finished(SearchThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    sj.execute()
    sj.search('foo')
    assert SearchThread_mock.return_value.search.call_args_list == [call('foo')]

@patch('upsies.jobs.search._SearchThread')
def test_search_after_finished(SearchThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    sj.execute()
    sj.finish()
    sj.search('foo')
    assert SearchThread_mock.return_value.search.call_args_list == []


def test_searching_status(tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    cb = Mock()
    sj.on_searching_status(cb)
    assert sj.is_searching is False
    sj.handle_searching_status(True)
    assert sj.is_searching is True
    assert cb.call_args_list == [call(True)]
    sj.handle_searching_status(False)
    assert sj.is_searching is False
    assert cb.call_args_list == [call(True), call(False)]


@patch('upsies.jobs.search._UpdateInfoThread')
@patch('upsies.jobs.search._SearchThread')
def test_search_results(SearchThread_mock, UpdateInfoThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    results = ('foo', 'bar', 'baz')
    cb = Mock()
    sj.on_search_results(cb)
    sj.execute()
    sj.handle_search_results(results)
    assert cb.call_args_list == [call(results)]
    assert UpdateInfoThread_mock.return_value.call_args_list == [call(results[0])]

@patch('upsies.jobs.search._UpdateInfoThread')
@patch('upsies.jobs.search._SearchThread')
def test_no_search_results(SearchThread_mock, UpdateInfoThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    results = ()
    cb = Mock()
    sj.on_search_results(cb)
    sj.execute()
    sj.handle_search_results(results)
    assert cb.call_args_list == [call(results)]
    assert UpdateInfoThread_mock.return_value.call_args_list == [call(None)]


def test_update_info(tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    cb = Mock()
    sj.on_info_updated(cb)
    sj.update_info('The Key', 'The Info')
    assert cb.call_args_list == [call('The Key', 'The Info')]


@patch('upsies.jobs.search._UpdateInfoThread')
def test_result_focused(UpdateInfoThread_mock, tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    sj.execute()
    sj.result_focused('The Result')
    assert UpdateInfoThread_mock.return_value.call_args_list == [call('The Result')]


def test_id_selected(tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert not sj.is_finished
    sj.id_selected('The ID')
    assert sj.is_finished
    assert sj.output == ('The ID',)

def test_id_selected_while_searching(tmp_path):
    sj = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert not sj.is_finished
    sj._is_searching = True
    sj.id_selected('The ID')
    assert not sj.is_finished
    assert sj.output == ()


def test_SearchThread_normalize_query():
    assert search._SearchThread._normalize_query(' The\tFoo \n') == 'the foo'


def test_SearchThread_stop():
    search_coro = AsyncMock()
    results_cb = Mock()
    error_cb = Mock()
    searching_cb = Mock()
    st = search._SearchThread(search_coro, results_cb, error_cb, searching_cb)
    st.start()
    assert st.is_alive
    st.stop()
    asyncio.get_event_loop().run_until_complete(st.join())
    assert not st.is_alive
    assert not st._loop.is_running()


def test_SearchThread_search_ignores_same_search_term():
    search_coro = AsyncMock()
    results_cb = Mock()
    error_cb = Mock()
    searching_cb = Mock()
    st = search._SearchThread(search_coro, results_cb, error_cb, searching_cb)
    st.start()
    assert st._query == ''
    with patch.object(st, 'unblock') as unblock_mock:
        st.search('The foo')
        assert unblock_mock.call_args_list == [call()]
        assert st._query == 'The foo'
        st.search('The  Foo')
        assert unblock_mock.call_args_list == [call()]
        assert st._query == 'The foo'
        st.search('The  FOO\n')
        assert unblock_mock.call_args_list == [call()]
        assert st._query == 'The foo'

def test_SearchThread_search_sets_off_new_search():
    search_coro = AsyncMock()
    results_cb = Mock()
    error_cb = Mock()
    searching_cb = Mock()
    st = search._SearchThread(search_coro, results_cb, error_cb, searching_cb)
    st.start()
    with patch.object(st, 'unblock') as unblock_mock:
        st.search('The Foo')
        assert unblock_mock.call_args_list == [call()]
        st.search('The Bar')
        assert st._query == 'The Bar'
        assert unblock_mock.call_args_list == [call(), call()]


def test_SearchThread_work():
    search_coro = AsyncMock()
    results_cb = Mock()
    error_cb = Mock()
    searching_cb = Mock()
    st = search._SearchThread(search_coro, results_cb, error_cb, searching_cb)
    with patch.object(st, '_delay_search', new_callable=AsyncMock) as delay_search_mock:
        st.start()
        st.search('asdf')
        time.sleep(0.1)
        assert delay_search_mock.call_args_list == [call()]


def test_SearchThread_delay_search():
    search_coro = AsyncMock()
    results_cb = Mock()
    error_cb = Mock()
    searching_cb = Mock()
    st = search._SearchThread(search_coro, results_cb, error_cb, searching_cb)
    with patch.object(st, '_delay', new_callable=AsyncMock) as delay_mock:
        delay_mock.return_value = 0.1
        search_coro.return_value = ('Foo', 'Bar')
        st.start()
        st.search('a')
        st.search('b')
        assert results_cb.call_args_list == []
        assert error_cb.call_args_list == []
        assert searching_cb.call_args_list == []
        assert search_coro.call_args_list == []
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.2))
        assert results_cb.call_args_list == [call(()), call(('Foo', 'Bar'))]
        assert error_cb.call_args_list == []
        assert searching_cb.call_args_list == [call(True), call(False)]
        assert search_coro.call_args_list == [call('b')]

def test_SearchThread_delay_search_handles_RequestError():
    search_coro = AsyncMock()
    results_cb = Mock()
    error_cb = Mock()
    searching_cb = Mock()
    st = search._SearchThread(search_coro, results_cb, error_cb, searching_cb)
    with patch.object(st, '_delay', new_callable=AsyncMock) as delay_mock:
        delay_mock.return_value = 0.1
        search_coro.side_effect = errors.RequestError('Bam!')
        st.start()
        st.search('a')
        assert results_cb.call_args_list == []
        assert error_cb.call_args_list == []
        assert searching_cb.call_args_list == []
        assert search_coro.call_args_list == []
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.2))
        assert results_cb.call_args_list == [call(()), call(())]
        assert isinstance(error_cb.call_args_list[0][0][0], errors.RequestError)
        assert str(error_cb.call_args_list[0][0][0]) == 'Bam!'
        assert searching_cb.call_args_list == [call(True), call(False)]
        assert search_coro.call_args_list == [call('a')]


@pytest.mark.parametrize(
    argnames=('query', 'exp_query', 'exp_kwargs'),
    argvalues=(
        ('\tThe    Foo\n', 'The Foo', {}),
        ('The Foo year:2000', 'The Foo', {'year': '2000'}),
        ('The Foo type:movie', 'The Foo', {'type': 'movie'}),
        ('The Foo type:series', 'The Foo', {'type': 'series'}),
        ('The Foo type:tv', 'The Foo', {'type': 'series'}),
        ('The Foo type:show', 'The Foo', {'type': 'series'}),
        ('The Foo type:episode', 'The Foo', {'type': 'series'}),
        ('The Foo type:season', 'The Foo', {'type': 'series'}),
        ('1984 type:movie year:2000', '1984', {'type': 'movie', 'year': '2000'}),
        ('Bar type:something year:else', 'Bar type:something year:else', {}),
    ),
    ids=lambda val: str(val),
)
def test_SearchThread_parse_query(query, exp_query, exp_kwargs):
    args, kwargs = search._SearchThread._parse_query(query)
    assert args == exp_query
    assert kwargs == exp_kwargs


@patch('asyncio.sleep')
def test_SearchThread_delay_for_first_search(sleep_mock):
    search_coro = AsyncMock()
    results_cb = Mock()
    error_cb = Mock()
    searching_cb = Mock()
    st = search._SearchThread(search_coro, results_cb, error_cb, searching_cb)
    st._first_search = True
    asyncio.get_event_loop().run_until_complete(st._delay())
    assert sleep_mock.call_args_list == []
    assert st._first_search is False

@patch('asyncio.sleep', new_callable=AsyncMock)
def test_SearchThread_delay_for_subsequent_searches(sleep_mock):
    search_coro = AsyncMock()
    results_cb = Mock()
    error_cb = Mock()
    searching_cb = Mock()
    st = search._SearchThread(search_coro, results_cb, error_cb, searching_cb)
    st._first_search = False
    asyncio.get_event_loop().run_until_complete(st._delay())
    assert sleep_mock.call_args_list == [call(st._seconds_between_searches)]
    assert st._first_search is False


def test_UpdateInfoThread_stop():
    uit = search._UpdateInfoThread()
    uit.start()
    assert uit.is_alive
    uit.stop()
    asyncio.get_event_loop().run_until_complete(uit.join())
    assert not uit.is_alive
    assert not uit._loop.is_running()


def test_UpdateInfoThread_updating_cancels_previous_update_task():
    uit = search._UpdateInfoThread()
    uit.start()
    uit._update_task = Mock(done=lambda: False)
    uit(Mock())
    assert uit._update_task.cancel.call_args_list == [call()]

def test_UpdateInfoThread_updating_does_not_cancel_previous_update_task():
    # Previous task is done
    uit = search._UpdateInfoThread()
    uit.start()
    uit._update_task = Mock(done=lambda: True)
    uit(Mock())
    assert uit._update_task.cancel.call_args_list == []
    uit.stop()

    # No previous task exists
    uit = search._UpdateInfoThread()
    uit.start()
    uit._update_task = None
    uit(Mock())
    assert uit._update_task is None
    uit.stop()

def test_UpdateInfoThread_updating_sets_result():
    uit = search._UpdateInfoThread()
    uit.start()
    search_result = Mock()
    uit(search_result)
    assert uit._result is search_result

def test_UpdateInfoThread_updating_calls_unblock():
    uit = search._UpdateInfoThread()
    uit.start()
    search_result = Mock()
    with patch.object(uit, 'unblock') as unblock_mock:
        uit(search_result)
        assert unblock_mock.call_args_list == [call()]

def test_UpdateInfoThread_updating_sets_noncallable_values_immediately():
    targets = {'year': Mock(), 'summary': Mock(), 'cast': Mock()}
    uit = search._UpdateInfoThread(**targets)
    uit.start()
    search_result = Mock(
        year=2000,
        summary='Something happens and then something else happens.',
        cast=AsyncMock(),
    )
    uit(search_result)
    assert targets['year'].call_args_list == [call('2000')]
    assert targets['summary'].call_args_list == [call('Something happens and then something else happens.')]

def test_UpdateInfoThread_updating_handles_search_result_being_None():
    targets = {'year': Mock(), 'summary': Mock(), 'cast': Mock()}
    uit = search._UpdateInfoThread(**targets)
    uit.start()
    search_result = None
    uit(search_result)
    assert targets['year'].call_args_list == []
    assert targets['summary'].call_args_list == []
    assert targets['cast'].call_args_list == []


def test_UpdateInfoThread_work_handles_no_search_result():
    targets = {'year': Mock(), 'summary': Mock(), 'cast': Mock()}
    uit = search._UpdateInfoThread(**targets)
    uit._result = None
    uit.work()
    for cb in targets.values():
        assert cb.call_args_list == [call('')]

def test_UpdateInfoThread_work_handles_no_targets():
    targets = {'year': Mock(), 'summary': Mock(), 'cast': Mock()}
    uit = search._UpdateInfoThread(**targets)
    uit._result = Mock()
    with patch.object(uit, '_make_update_tasks') as make_update_tasks_mock:
        make_update_tasks_mock.return_value = ()
        uit.work()
    for cb in targets.values():
        assert cb.call_args_list == []

def test_UpdateInfoThread_work_gathers_update_tasks():
    targets = {'year': Mock(), 'summary': Mock(), 'cast': Mock()}
    uit = search._UpdateInfoThread(**targets)
    asyncio.set_event_loop(uit._loop)
    uit._result = Mock()
    update_tasks = (AsyncMock(), AsyncMock(), AsyncMock())
    with patch.object(uit, '_make_update_tasks') as make_update_tasks_mock:
        make_update_tasks_mock.return_value = update_tasks
        uit.work()
    for task in update_tasks:
        assert task.call_args_list == [call()]

def test_UpdateInfoThread_work_tries_again_on_CancelledError():
    targets = {'year': Mock(), 'summary': Mock(), 'cast': Mock()}
    uit = search._UpdateInfoThread(**targets)
    asyncio.set_event_loop(uit._loop)
    uit._result = Mock()
    update_tasks = (
        AsyncMock(return_value='one'),
        AsyncMock(
            side_effect=(
                asyncio.CancelledError(),
                asyncio.CancelledError(),
                'two',
            ),
        ),
        AsyncMock(
            side_effect=(
                asyncio.CancelledError(),
                'three',
            ),
        ),
    )
    with patch.object(uit, '_make_update_tasks') as make_update_tasks_mock:
        make_update_tasks_mock.return_value = update_tasks
        uit.work()
    for task in update_tasks:
        assert task.call_args_list == [call(), call(), call()]


def test_make_update_tasks():
    targets = {'year': Mock(), 'summary': Mock(), 'cast': Mock(), 'country': Mock()}
    uit = search._UpdateInfoThread(**targets)
    uit._result = Mock(
        year=2003,
        summary='Something happens.',
        cast=AsyncMock(return_value=('She', 'He', 'Doggo')),
        country=AsyncMock(return_value='Antarctica'),
    )
    with patch.object(uit, '_make_update_task') as make_update_task_mock:
        make_update_task_mock.side_effect = ('cast task', 'country task')
        tasks = uit._make_update_tasks()
        assert make_update_task_mock.call_args_list == [
            call(
                cache_key=(uit._result.id, 'cast'),
                value_getter=uit._result.cast,
                callback=targets['cast'],
            ),
            call(
                cache_key=(uit._result.id, 'country'),
                value_getter=uit._result.country,
                callback=targets['country'],
            ),
        ]
        assert tasks == ['cast task', 'country task']


@patch('asyncio.sleep', new_callable=AsyncMock)
def test_make_update_task_gets_value_from_value_getter(sleep_mock):
    search._UpdateInfoThread._cache.clear()
    uit = search._UpdateInfoThread()
    asyncio.set_event_loop(uit._loop)
    value_getter = AsyncMock(return_value='1234')
    callback = Mock()
    task = uit._make_update_task(
        cache_key=('id', 'key'),
        value_getter=value_getter,
        callback=callback,
    )
    uit._cache.clear()
    asyncio.get_event_loop().run_until_complete(task)
    assert value_getter.call_args_list == [call()]
    assert callback.call_args_list == [call('Loading...'), call('1234')]
    assert uit._cache[('id', 'key')] == '1234'
    assert sleep_mock.call_args_list == [call(search._UpdateInfoThread._delay_between_updates)]
    asyncio.get_event_loop().close()

@patch('asyncio.sleep', new_callable=AsyncMock)
def test_make_update_task_handles_RequestError(sleep_mock):
    search._UpdateInfoThread._cache.clear()
    uit = search._UpdateInfoThread()
    asyncio.set_event_loop(uit._loop)
    value_getter = AsyncMock(side_effect=errors.RequestError('Nah'))
    callback = Mock()
    task = uit._make_update_task(
        cache_key=('id', 'key'),
        value_getter=value_getter,
        callback=callback,
    )
    asyncio.get_event_loop().run_until_complete(task)
    assert value_getter.call_args_list == [call()]
    assert callback.call_args_list == [call('Loading...'), call('ERROR: Nah')]
    assert uit._cache[('id', 'key')] == 'ERROR: Nah'
    assert sleep_mock.call_args_list == [call(search._UpdateInfoThread._delay_between_updates)]

@patch('asyncio.sleep', new_callable=AsyncMock)
def test_make_update_task_gets_value_from_cache(sleep_mock):
    search._UpdateInfoThread._cache.clear()
    uit = search._UpdateInfoThread()
    asyncio.set_event_loop(uit._loop)
    value_getter = AsyncMock(return_value='1234')
    callback = Mock()
    task = uit._make_update_task(
        cache_key=('id', 'key'),
        value_getter=value_getter,
        callback=callback,
    )
    uit._cache[('id', 'key')] = '1234'
    asyncio.get_event_loop().run_until_complete(task)
    assert value_getter.call_args_list == []
    assert callback.call_args_list == [call('1234')]
    assert uit._cache[('id', 'key')] == '1234'
    assert sleep_mock.call_args_list == []


def test_value_as_string_with_string():
    assert search._UpdateInfoThread._value_as_string('foo bar baz') == 'foo bar baz'

def test_value_as_string_with_iterable():
    assert search._UpdateInfoThread._value_as_string(('foo', 'bar', 'baz')) == 'foo, bar, baz'
    assert search._UpdateInfoThread._value_as_string(['foo', 2, {3}]) == 'foo, 2, {3}'

def test_value_as_string_with_other_type():
    assert search._UpdateInfoThread._value_as_string(type) == str(type)
