import asyncio
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


@pytest.fixture
def job(tmp_path):
    with patch('upsies.jobs.search._SearchThread', Mock()):
        with patch('upsies.jobs.search._UpdateInfoThread', Mock()):
            return search.SearchDbJob(
                homedir=tmp_path,
                ignore_cache=False,
                db='imdb',
                content_path='path/to/foo',
            )


def test_name(job):
    assert job.name == 'imdb-id'


def test_label(job):
    assert job.label == 'IMDb ID'


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
def test_make_query_from_path(guessit_mock, tmp_path, guess, exp_query):
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
    assert sj._search_thread.start.call_args_list == []

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
        'director func',
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
        director='director func',
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
        call('director'),
        call('cast'),
        call('country'),
    ]


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


def test_execute_starts_threads_in_correct_order(job):
    cbs = Mock()
    job._search_thread.start = cbs.start_search_thread
    job._update_info_thread.start = cbs.start_update_info_thread
    assert cbs.mock_calls == []
    job.execute()
    assert cbs.mock_calls == [
        call.start_update_info_thread(),
        call.start_search_thread(),
    ]


def test_finish(job):
    assert not job.is_finished
    job.finish()
    assert job.is_finished
    assert job._search_thread.stop.call_args_list == [call()]
    assert job._update_info_thread.stop.call_args_list == [call()]


def test_wait(job):
    job._search_thread.join = AsyncMock()
    job._update_info_thread.join = AsyncMock()
    asyncio.get_event_loop().call_soon(job.finish)
    asyncio.get_event_loop().run_until_complete(job.wait())
    assert job.is_finished
    assert job._search_thread.join.call_args_list == [call()]
    assert job._update_info_thread.join.call_args_list == [call()]


def test_search_before_finished(job):
    job.execute()
    job.search('foo')
    assert job._search_thread.search.call_args_list == [call('foo')]

def test_search_after_finished(job):
    job.execute()
    job.finish()
    job.search('foo')
    assert job._search_thread.search.call_args_list == []

def test_search_updates_query_property(job):
    job.execute()
    job.search('Foo')
    assert job.query == 'Foo'
    job.search('BAR')
    assert job.query == 'BAR'
    job.finish()
    job.search('baZ')
    assert job.query == 'BAR'


def test_searching_status(job):
    cb = Mock()
    job.on_searching_status(cb)
    assert job.is_searching is False
    job.handle_searching_status(True)
    assert job.is_searching is True
    assert cb.call_args_list == [call(True)]
    job.handle_searching_status(False)
    assert job.is_searching is False
    assert cb.call_args_list == [call(True), call(False)]


def test_search_results(job):
    results = ('foo', 'bar', 'baz')
    cb = Mock()
    job.on_search_results(cb)
    job.execute()
    job.handle_search_results(results)
    assert cb.call_args_list == [call(results)]
    assert job._update_info_thread.set_result.call_args_list == [call(results[0])]

def test_no_search_results(job):
    results = ()
    cb = Mock()
    job.on_search_results(cb)
    job.execute()
    job.handle_search_results(results)
    assert cb.call_args_list == [call(results)]
    assert job._update_info_thread.set_result.call_args_list == [call(None)]


def test_update_info(job):
    cb = Mock()
    job.on_info_updated(cb)
    job.update_info('The Key', 'The Info')
    assert cb.call_args_list == [call('The Key', 'The Info')]


def test_result_focused(job):
    job.result_focused('The Result')
    assert job._update_info_thread.set_result.call_args_list == [call('The Result')]


def test_id_selected(job):
    assert not job.is_finished
    job.id_selected('The ID')
    assert job.is_finished
    assert job.output == ('The ID',)

def test_id_selected_while_searching(job):
    assert not job.is_finished
    job._is_searching = True
    job.id_selected('The ID')
    assert not job.is_finished
    assert job.output == ()


@pytest.fixture
def search_thread():
    return search._SearchThread(
        search_coro=AsyncMock(),
        results_callback=Mock(),
        error_callback=Mock(),
        searching_callback=Mock(),
    )


def test_SearchThread_query():
    st = search._SearchThread(
        query=' The\tFoo \n',
        search_coro=AsyncMock(),
        results_callback=Mock(),
        error_callback=Mock(),
        searching_callback=Mock(),
    )
    assert st.query == 'the foo'


def test_SearchThread_initialize():
    search_coro = AsyncMock()
    results_cb = Mock()
    error_cb = Mock()
    searching_cb = Mock()
    search_thread = search._SearchThread(
        search_coro=search_coro,
        results_callback=results_cb,
        error_callback=error_cb,
        searching_callback=searching_cb,
    )
    assert search_thread._search_coro == search_coro
    assert search_thread._results_callback == results_cb
    assert search_thread._searching_callback == searching_cb
    assert search_thread._error_callback == error_cb
    assert search_thread._first_search is True
    assert search_thread.query == ''


def test_SearchThread_search(search_thread):
    search_thread.start()
    with patch.multiple(search_thread, unblock=Mock(), cancel_work=Mock()):
        search_thread.search('The Foo')
        assert search_thread.cancel_work.call_args_list == [call()]
        assert search_thread.unblock.call_args_list == [call()]
        search_thread.search('The Bar')
        assert search_thread.cancel_work.call_args_list == [call(), call()]
        assert search_thread.unblock.call_args_list == [call(), call()]


@pytest.mark.asyncio
async def test_SearchThread_work(search_thread):
    mock_methods = {
        '_delay': AsyncMock(),
        '_results_callback': Mock(),
        '_searching_callback': Mock(),
        '_parse_query': Mock(return_value=('The Foo', {'year': '2002'})),
        '_search_coro': AsyncMock(return_value=('The Foo', 'The Foo 2')),
        '_error_callback': Mock(),
        '_query': 'The Foo year:2002',
    }
    mocks = Mock(**mock_methods)
    with patch.multiple(search_thread, **mock_methods):
        await search_thread.work()
        assert mocks.mock_calls == [
            call._delay(),
            call._results_callback(()),
            call._searching_callback(True),
            call._parse_query('The Foo year:2002'),
            call._search_coro('The Foo', year='2002'),
            call._searching_callback(False),
            call._results_callback(('The Foo', 'The Foo 2')),
        ]

@pytest.mark.asyncio
async def test_SearchThread_work_handles_RequestError(search_thread):
    mock_methods = {
        '_delay': AsyncMock(),
        '_results_callback': Mock(),
        '_searching_callback': Mock(),
        '_parse_query': Mock(return_value=('The Foo', {'year': '2002'})),
        '_search_coro': AsyncMock(side_effect=errors.RequestError('No')),
        '_error_callback': Mock(),
        '_query': 'The Foo year:2002',
    }
    mocks = Mock(**mock_methods)
    with patch.multiple(search_thread, **mock_methods):
        await search_thread.work()
        assert mocks.mock_calls == [
            call._delay(),
            call._results_callback(()),
            call._searching_callback(True),
            call._parse_query('The Foo year:2002'),
            call._search_coro('The Foo', year='2002'),
            call._error_callback(errors.RequestError('No')),
            call._searching_callback(False),
            call._results_callback(()),
        ]


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


@pytest.fixture
def info_thread():
    return search._UpdateInfoThread()


def test_UpdateInfoThread_set_result_schedules_update(info_thread):
    with patch.multiple(info_thread, unblock=Mock(), cancel_work=Mock()):
        assert info_thread._result is None
        assert info_thread.cancel_work.call_args_list == []
        assert info_thread.unblock.call_args_list == []
        info_thread.set_result('mock result')
        assert info_thread._result == 'mock result'
        assert info_thread.cancel_work.call_args_list == [call()]
        assert info_thread.unblock.call_args_list == [call()]

def test_UpdateInfoThread_set_result_updates_available_info_immediately(info_thread):
    targets = {
        'title': Mock(),
        'year': Mock(),
        'summary': Mock(),
    }
    result = Mock(
        title='The Foo',
        year='2002',
        summary=AsyncMock(),
    )
    with patch.multiple(info_thread, unblock=Mock(), cancel_work=Mock(), _targets=targets):
        info_thread.set_result(result)
    assert targets['title'].call_args_list == [call('The Foo')]
    assert targets['year'].call_args_list == [call('2002')]
    assert targets['summary'].call_args_list == []


@pytest.mark.asyncio
async def test_UpdateInfoThread_work_without_result_set(info_thread):
    targets = {
        'title': Mock(),
        'year': Mock(),
        'summary': Mock(),
    }
    info_thread._result = None
    with patch.multiple(info_thread, _targets=targets):
        await info_thread.work()
    assert targets['title'].call_args_list == [call('')]
    assert targets['year'].call_args_list == [call('')]
    assert targets['summary'].call_args_list == [call('')]

@pytest.mark.asyncio
async def test_UpdateInfoThread_work_with_result_set(info_thread):
    targets = {
        'title': Mock(),
        'year': Mock(),
        'summary': Mock(),
    }
    update_tasks = (AsyncMock(), AsyncMock())
    info_thread._result = 'mock result'
    with patch.multiple(info_thread, _targets=targets, _make_update_tasks=Mock(return_value=update_tasks)):
        await info_thread.work()
        assert info_thread._make_update_tasks.call_args_list == [call()]
    for task in update_tasks:
        assert task.call_args_list == [call()]
    assert targets['title'].call_args_list == []
    assert targets['year'].call_args_list == []
    assert targets['summary'].call_args_list == []


def test_UpdateInfoThread_make_update_tasks(info_thread):
    targets = {'year': Mock(), 'summary': Mock(), 'cast': Mock(), 'country': Mock()}
    info_thread._result = Mock(
        id='123',
        year=2003,
        summary='Something happens.',
        cast=AsyncMock(return_value=('She', 'He', 'Doggo')),
        country=AsyncMock(return_value='Antarctica'),
    )
    with patch.multiple(info_thread, _make_update_task=Mock(), _targets=targets):
        info_thread._make_update_task.side_effect = ('cast task', 'country task')
        assert info_thread._make_update_tasks() == ['cast task', 'country task']
        assert info_thread._make_update_task.call_args_list == [
            call(
                cache_key=(info_thread._result.id, 'cast'),
                value_getter=info_thread._result.cast,
                callback=targets['cast'],
            ),
            call(
                cache_key=(info_thread._result.id, 'country'),
                value_getter=info_thread._result.country,
                callback=targets['country'],
            ),
        ]


def test_UpdateInfoThread_make_update_task_gets_value_from_value_getter(info_thread):
    mocks = Mock(
        value_getter=AsyncMock(return_value='The Value'),
        callback=Mock(),
        sleep_mock=AsyncMock(),
    )
    info_thread._cache.clear()
    with patch('asyncio.sleep', mocks.sleep_mock):
        info_thread._loop.run_until_complete(
            info_thread._make_update_task(
                cache_key=('id', 'key'),
                value_getter=mocks.value_getter,
                callback=mocks.callback,
            )
        )
    assert mocks.mock_calls == [
        call.callback('Loading...'),
        call.sleep_mock(info_thread._delay_between_updates),
        call.value_getter(),
        call.callback('The Value'),
    ]
    assert info_thread._cache[('id', 'key')] == 'The Value'

def test_UpdateInfoThread_make_update_task_handles_RequestError(info_thread):
    mocks = Mock(
        value_getter=AsyncMock(side_effect=errors.RequestError('Nah')),
        callback=Mock(),
        sleep_mock=AsyncMock(),
    )
    info_thread._cache.clear()
    with patch('asyncio.sleep', mocks.sleep_mock):
        info_thread._loop.run_until_complete(
            info_thread._make_update_task(
                cache_key=('id', 'key'),
                value_getter=mocks.value_getter,
                callback=mocks.callback,
            )
        )
    assert mocks.mock_calls == [
        call.callback('Loading...'),
        call.sleep_mock(info_thread._delay_between_updates),
        call.value_getter(),
        call.callback('ERROR: Nah'),
    ]
    assert info_thread._cache == {}


def test_UpdateInfoThread_make_update_task_gets_value_from_cache(info_thread):
    mocks = Mock(
        value_getter=AsyncMock(return_value='The Value'),
        callback=Mock(),
        sleep_mock=AsyncMock(),
    )
    info_thread._cache[('id', 'key')] = 'The Other Value'
    with patch('asyncio.sleep', mocks.sleep_mock):
        info_thread._loop.run_until_complete(
            info_thread._make_update_task(
                cache_key=('id', 'key'),
                value_getter=mocks.value_getter,
                callback=mocks.callback,
            )
        )
    assert mocks.mock_calls == [
        call.callback('The Other Value'),
    ]
    assert info_thread._cache[('id', 'key')] == 'The Other Value'


def test_value_as_string_with_string():
    assert search._UpdateInfoThread._value_as_string('foo bar baz') == 'foo bar baz'

def test_value_as_string_with_iterable():
    assert search._UpdateInfoThread._value_as_string(('foo', 'bar', 'baz')) == 'foo, bar, baz'
    assert search._UpdateInfoThread._value_as_string(['foo', 2, {3}]) == 'foo, 2, {3}'

def test_value_as_string_with_other_type():
    assert search._UpdateInfoThread._value_as_string(type) == str(type)
