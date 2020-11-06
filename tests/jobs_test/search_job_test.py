import asyncio
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.jobs import search
from upsies.tools.dbs import Query


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
def job(tmp_path, mocker):
    mocker.patch('upsies.jobs.search._Searcher', Mock(return_value=Mock(wait=AsyncMock())))
    mocker.patch('upsies.jobs.search._InfoUpdater', Mock(return_value=Mock(wait=AsyncMock())))
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


def test_query(job):
    assert isinstance(job.query, Query)


def test_unknown_db(tmp_path):
    with pytest.raises(ValueError, match=r'^Unknown database: foo$'):
        search.SearchDbJob(
            homedir=tmp_path,
            ignore_cache=False,
            db='foo',
            content_path='path/to/foo',
        )


def test_initialize_creates_searcher(tmp_path, mocker):
    Searcher_mock = mocker.patch('upsies.jobs.search._Searcher', Mock())
    job = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert job._searcher is Searcher_mock.return_value
    assert Searcher_mock.call_args_list == [call(
        search_coro=search.dbs.imdb.search,
        results_callback=job.handle_search_results,
        error_callback=job.error,
        searching_callback=job.handle_searching_status,
    )]

def test_initialize_creates_info_updater(tmp_path, mocker):
    InfoUpdater_mock = mocker.patch('upsies.jobs.search._InfoUpdater', Mock())
    make_update_info_func_mock = mocker.patch(
        'upsies.jobs.search.SearchDbJob._make_update_info_func',
        Mock(
            side_effect=(
                'id func',
                'summary func',
                'title_original func',
                'title_english func',
                'keywords func',
                'director func',
                'cast func',
                'country func',
            ),
        )
    )
    job = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    assert job._info_updater is InfoUpdater_mock.return_value
    assert InfoUpdater_mock.call_args_list == [call(
        error_callback=job.error,
        targets={
            'id': 'id func',
            'summary': 'summary func',
            'title_original': 'title_original func',
            'title_english': 'title_english func',
            'keywords': 'keywords func',
            'director': 'director func',
            'cast': 'cast func',
            'country': 'country func',
        },
    )]
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


def test_make_update_info_func(tmp_path, mocker):
    mocker.patch('upsies.jobs.search.SearchDbJob.update_info')
    job = search.SearchDbJob(
        homedir=tmp_path,
        ignore_cache=False,
        db='imdb',
        content_path='path/to/foo',
    )
    func = job._make_update_info_func('key')
    func('value 1')
    assert job.update_info.call_args_list == [call('key', 'value 1')]
    func('value 2')
    assert job.update_info.call_args_list == [call('key', 'value 1'), call('key', 'value 2')]


def test_execute_does_initial_search(job):
    assert job._searcher.search.call_args_list == []
    job.execute()
    assert job._searcher.search.call_args_list == [call(job.query)]


def test_finish_cancels_info_updater(job):
    job._info_updater = Mock()
    job.finish()
    assert job._info_updater.cancel.call_args_list == [call()]


@pytest.mark.asyncio
async def test_wait(job):
    assert job._searcher.wait.call_args_list == []
    assert job._info_updater.wait.call_args_list == []
    asyncio.get_event_loop().call_soon(job.finish)
    await job.wait()
    assert job.is_finished
    assert job._searcher.wait.call_args_list == [call()]
    assert job._info_updater.wait.call_args_list == [call()]


def test_search_before_finished(job):
    job.search('foo')
    assert job._searcher.search.call_args_list == [call(Query(title='foo'))]

def test_search_after_finished(job):
    job.finish()
    job.search('foo')
    assert job._searcher.search.call_args_list == []

def test_search_updates_query_property(job):
    job.search('Foo')
    assert job.query == Query(title='Foo')
    job.search('BAR')
    assert job.query == Query(title='BAR')
    job.finish()
    job.search('baZ')
    assert job.query == Query(title='BAR')


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
    job.handle_search_results(results)
    assert job._info_updater.set_result.call_args_list == [call(results[0])]
    assert cb.call_args_list == [call(results)]

def test_no_search_results(job):
    results = ()
    cb = Mock()
    job.on_search_results(cb)
    job.handle_search_results(results)
    assert job._info_updater.set_result.call_args_list == [call(None)]
    assert cb.call_args_list == [call(results)]


def test_update_info(job):
    cb = Mock()
    job.on_info_updated(cb)
    job.update_info('The Key', 'The Info')
    assert cb.call_args_list == [call('The Key', 'The Info')]


def test_result_focused(job):
    job.result_focused('The Result')
    assert job._info_updater.set_result.call_args_list == [call('The Result')]


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
async def searcher():
    searcher = search._Searcher(
        search_coro=AsyncMock(),
        results_callback=Mock(),
        error_callback=Mock(),
        searching_callback=Mock(),
    )
    yield searcher
    await searcher.wait()


@pytest.mark.asyncio
async def test_Searcher_wait_while_not_searching(searcher):
    searcher._search_task = None
    await searcher.wait()
    assert searcher._search_task is None

@pytest.mark.asyncio
async def test_Searcher_wait_while_searching(searcher):
    searcher._search_task = asyncio.ensure_future(AsyncMock())
    await searcher.wait()
    assert searcher._search_task.done()


def test_Searcher_search_while_not_searching(searcher, mocker):
    mocker.patch.object(searcher, '_search', Mock(return_value=AsyncMock()))
    searcher._search_task = None
    searcher.search('mock query')
    assert searcher._search.call_args_list == [call('mock query')]
    assert isinstance(searcher._search_task, asyncio.Task)
    assert not searcher._search_task.done()
    assert not searcher._search_task.cancelled()

def test_Searcher_search_while_searching(searcher, mocker):
    mocker.patch.object(searcher, '_search', Mock(return_value=AsyncMock()))
    old_task = searcher._search_task = Mock()
    searcher.search('mock query')
    assert searcher._search.call_args_list == [call('mock query')]
    assert isinstance(searcher._search_task, asyncio.Task)
    new_task = searcher._search_task
    assert new_task is not old_task
    assert old_task.cancel.call_args_list == [call()]
    assert not new_task.done()
    assert not new_task.cancelled()


@pytest.mark.asyncio
async def test_Searcher__search_reports_results(searcher, mocker):
    mock_methods = {
        '_results_callback': Mock(),
        '_searching_callback': Mock(),
        '_delay': AsyncMock(),
        '_search_coro': AsyncMock(return_value=('mock result 1', 'mock result 2')),
        '_error_callback': Mock(),
    }
    mocks = Mock(**mock_methods)
    mocker.patch.multiple(searcher, **mock_methods)
    await searcher._search('mock query')
    assert mocks.mock_calls == [
        call._results_callback(()),
        call._searching_callback(True),
        call._delay(),
        call._search_coro('mock query'),
        call._searching_callback(False),
        call._results_callback(('mock result 1', 'mock result 2')),
    ]

@pytest.mark.asyncio
async def test_Searcher__search_reports_error(searcher, mocker):
    mock_methods = {
        '_results_callback': Mock(),
        '_searching_callback': Mock(),
        '_delay': AsyncMock(),
        '_search_coro': AsyncMock(side_effect=errors.RequestError('internet is down')),
        '_error_callback': Mock(),
    }
    mocks = Mock(**mock_methods)
    mocker.patch.multiple(searcher, **mock_methods)
    await searcher._search('mock query')
    assert mocks.mock_calls == [
        call._results_callback(()),
        call._searching_callback(True),
        call._delay(),
        call._search_coro('mock query'),
        call._error_callback(errors.RequestError('internet is down')),
        call._searching_callback(False),
        call._results_callback(()),
    ]


@pytest.mark.asyncio
async def test_Searcher_delay_sleeps(searcher, mocker):
    mocker.patch('upsies.jobs.search.time_monotonic', Mock(side_effect=(1003, 1003.001)))
    sleep_mock = mocker.patch('asyncio.sleep', new_callable=AsyncMock)
    searcher._min_seconds_between_searches = 5
    searcher._previous_search_time = 1000
    await searcher._delay()
    assert sleep_mock.call_args_list == [call(2)]
    assert searcher._previous_search_time == 1003.001

@pytest.mark.asyncio
async def test_Searcher_delay_does_not_sleep(searcher, mocker):
    mocker.patch('upsies.jobs.search.time_monotonic', Mock(side_effect=(1006, 1006.001)))
    sleep_mock = mocker.patch('asyncio.sleep', new_callable=AsyncMock)
    searcher._min_seconds_between_searches = 5
    searcher._previous_search_time = 1000
    await searcher._delay()
    assert sleep_mock.call_args_list == []
    assert searcher._previous_search_time == 1006.001


@pytest.fixture
async def info_updater():
    info_updater = search._InfoUpdater(
        targets={},
        error_callback=Mock(),
    )
    yield info_updater
    await info_updater.wait()


@pytest.mark.asyncio
async def test_InfoUpdater_cancel_while_not_updating(info_updater):
    info_updater._update_task = None
    info_updater.cancel()
    await asyncio.sleep(0)
    assert info_updater._update_task is None

@pytest.mark.asyncio
async def test_InfoUpdater_cancel_while_updating(info_updater):
    info_updater._update_task = asyncio.ensure_future(asyncio.sleep(10))
    info_updater.cancel()
    await info_updater.wait()
    assert info_updater._update_task.cancelled()


@pytest.mark.asyncio
async def test_InfoUpdater_wait_while_not_updating(info_updater):
    info_updater._update_task = None
    await info_updater.wait()
    assert info_updater._update_task is None

@pytest.mark.asyncio
async def test_InfoUpdater_wait_while_updating(info_updater):
    info_updater._update_task = asyncio.ensure_future(asyncio.sleep(0.1))
    await info_updater.wait()
    assert info_updater._update_task.done()


@pytest.mark.asyncio
async def test_InfoUpdater_set_result_cancels_previous_update_task(info_updater, mocker):
    old_update_task = info_updater._update_task = asyncio.ensure_future(asyncio.sleep(10))
    info_updater.set_result('mock result')
    await asyncio.sleep(0)  # _update_task.cancel() to propagate
    assert old_update_task.cancelled()
    assert info_updater._update_task is not old_update_task

@pytest.mark.asyncio
async def test_InfoUpdater_set_result_does_not_cancel_previous_update_task(info_updater, mocker):
    info_updater._update_task = None
    info_updater.set_result('mock result')
    assert isinstance(info_updater._update_task, asyncio.Task)

@pytest.mark.asyncio
async def test_InfoUpdater_set_result_sets_result(info_updater, mocker):
    info_updater.set_result('mock result 1')
    assert info_updater._result == 'mock result 1'
    task1 = info_updater._update_task
    assert isinstance(task1, asyncio.Task)
    info_updater.set_result('mock result 2')
    assert info_updater._result == 'mock result 2'
    task2 = info_updater._update_task
    assert isinstance(task2, asyncio.Task)
    assert task1 is not task2

@pytest.mark.asyncio
async def test_InfoUpdater_set_result_calls_targets_with_no_result_set(info_updater, mocker):
    cbs = Mock()
    info_updater._targets = {
        'title': cbs.title,
        'year': cbs.year,
        'genre': cbs.genre,
    }
    info_updater.set_result(None)
    assert cbs.mock_calls == [
        call.title(''),
        call.year(''),
        call.genre(''),
    ]
    assert info_updater._update_task is None

@pytest.mark.asyncio
async def test_InfoUpdater_set_result_calls_targets_with_result_set(info_updater, mocker):
    mock_update = Mock(return_value=AsyncMock())
    mocker.patch.object(info_updater, '_update', mock_update)
    cbs = Mock()
    info_updater._targets = {
        'title': cbs.title,
        'year': cbs.year,
        'genre': cbs.genre,
    }
    result = Mock(
        title='The Foo',
        year='2015',
        genre=AsyncMock(return_value='bar'),
    )
    old_update_task = info_updater._update_task
    info_updater.set_result(result)
    assert cbs.mock_calls == [
        call.title('The Foo'),
        call.year('2015'),
    ]
    assert old_update_task is not info_updater._update_task
    assert isinstance(info_updater._update_task, asyncio.Task)
    assert mock_update.call_args_list == [call()]


@pytest.mark.asyncio
async def test_InfoUpdater_update(info_updater, mocker):
    mocker.patch.object(info_updater, '_call_callback', Mock())
    info_updater._targets = {
        'title': Mock(),
        'year': Mock(),
        'genre': Mock(),
        'summary': Mock(),
    }
    info_updater._result = Mock(
        id='123',
        title='The Foo',
        year='2015',
        genre=AsyncMock(return_value=('She', 'He', 'Doggo')),
        summary=AsyncMock(return_value='Something happens.'),
    )
    info_updater._call_callback.side_effect = (
        info_updater._result.genre,
        info_updater._result.summary,
    )
    await info_updater._update()
    assert info_updater._call_callback.call_args_list == [
        call(
            cache_key=('123', 'genre'),
            value_getter=info_updater._result.genre,
            callback=info_updater._targets['genre'],
        ),
        call(
            cache_key=('123', 'summary'),
            value_getter=info_updater._result.summary,
            callback=info_updater._targets['summary'],
        ),
    ]
    assert info_updater._targets['title'].call_args_list == []
    assert info_updater._targets['year'].call_args_list == []
    assert info_updater._targets['genre'].call_args_list == []
    assert info_updater._targets['summary'].call_args_list == []


@pytest.mark.asyncio
async def test_UpdateInfoThread_call_callback_gets_value_from_value_getter(info_updater, mocker):
    mocks = Mock(
        value_getter=AsyncMock(return_value='The Value'),
        callback=Mock(),
        sleep_mock=AsyncMock(),
    )
    mocker.patch('asyncio.sleep', mocks.sleep_mock)
    info_updater._cache.clear()
    await info_updater._call_callback(
        cache_key=('id', 'key'),
        value_getter=mocks.value_getter,
        callback=mocks.callback,
    )
    assert mocks.mock_calls == [
        call.callback('Loading...'),
        call.sleep_mock(info_updater._delay_between_updates),
        call.value_getter(),
        call.callback('The Value'),
    ]
    assert info_updater._cache[('id', 'key')] == 'The Value'

@pytest.mark.asyncio
async def test_UpdateInfoThread_call_callback_gets_value_from_cache(info_updater, mocker):
    mocks = Mock(
        value_getter=AsyncMock(return_value='The Value'),
        callback=Mock(),
        sleep_mock=AsyncMock(),
    )
    mocker.patch('asyncio.sleep', mocks.sleep_mock)
    info_updater._cache[('id', 'key')] = 'The Cached Value'
    await info_updater._call_callback(
        callback=mocks.callback,
        value_getter=mocks.value_getter,
        cache_key=('id', 'key'),
    )
    assert mocks.mock_calls == [
        call.callback('The Cached Value'),
    ]
    assert info_updater._cache[('id', 'key')] == 'The Cached Value'

@pytest.mark.asyncio
async def test_UpdateInfoThread_call_callback_handles_RequestError(info_updater, mocker):
    mocks = Mock(
        value_getter=AsyncMock(side_effect=errors.RequestError('Nah')),
        callback=Mock(),
        error_callback=Mock(),
        sleep_mock=AsyncMock(),
    )
    info_updater._error_callback = mocks.error_callback
    mocker.patch('asyncio.sleep', mocks.sleep_mock)
    info_updater._cache.clear()
    await info_updater._call_callback(
        callback=mocks.callback,
        value_getter=mocks.value_getter,
        cache_key=('id', 'key'),
    )
    assert mocks.mock_calls == [
        call.callback('Loading...'),
        call.sleep_mock(info_updater._delay_between_updates),
        call.value_getter(),
        call.callback(''),
        call.error_callback(errors.RequestError('Nah')),
    ]
    assert info_updater._cache == {}


def test_value_as_string_with_string(info_updater):
    assert info_updater._value_as_string('foo bar baz') == 'foo bar baz'

def test_value_as_string_with_iterable(info_updater):
    assert info_updater._value_as_string(('foo', 'bar', 'baz')) == 'foo, bar, baz'
    assert info_updater._value_as_string(['foo', 2, {3}]) == 'foo, 2, {3}'

def test_value_as_string_with_other_type(info_updater):
    assert info_updater._value_as_string(type) == str(type)
