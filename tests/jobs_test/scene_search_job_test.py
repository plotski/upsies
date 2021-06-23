from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.jobs.scene import SceneSearchJob


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
async def make_SceneSearchJob(tmp_path):
    def make_SceneSearchJob(content_path=tmp_path, ignore_cache=False):
        return SceneSearchJob(
            home_directory=tmp_path,
            cache_directory=tmp_path,
            ignore_cache=ignore_cache,
            content_path=content_path,
        )
    return make_SceneSearchJob


def test_cache_id(make_SceneSearchJob):
    job = make_SceneSearchJob(content_path='path/to/Foo/')
    assert job.cache_id == 'Foo'


@pytest.mark.asyncio
async def test_execute(make_SceneSearchJob, mocker):
    job = make_SceneSearchJob()
    mocker.patch.object(job, '_search', AsyncMock())
    job.execute()
    await job._tasks[0]
    assert job._search.call_args_list == [call()]
    assert job.is_finished


@pytest.mark.asyncio
async def test_search_handles_SceneError_from_query(make_SceneSearchJob, mocker):
    job = make_SceneSearchJob()
    cb = Mock()
    job.signal.register('search_results', cb)
    from_string_mock = mocker.patch('upsies.utils.scene.SceneQuery.from_string',
                                    side_effect=errors.SceneError('no!'))
    search_mock = mocker.patch('upsies.utils.scene.search', AsyncMock())
    await job._search()
    assert from_string_mock.call_args_list == [call(job._content_path)]
    assert job.errors == (errors.SceneError('no!'),)
    assert job.is_finished
    assert search_mock.call_args_list == []
    assert cb.call_args_list == []

@pytest.mark.asyncio
async def test_search_handles_SceneError_from_search(make_SceneSearchJob, mocker):
    job = make_SceneSearchJob()
    cb = Mock()
    job.signal.register('search_results', cb)
    from_string_mock = mocker.patch('upsies.utils.scene.SceneQuery.from_string',
                                    return_value='mock query')
    search_mock = mocker.patch('upsies.utils.scene.search', AsyncMock(
        side_effect=errors.SceneError('no')))
    await job._search()
    assert from_string_mock.call_args_list == [call(job._content_path)]
    assert search_mock.call_args_list == [call('mock query')]
    assert job.output == ()
    assert job.errors == (errors.SceneError('no'),)
    assert job.exit_code == 1
    assert job.is_finished
    assert cb.call_args_list == []

@pytest.mark.asyncio
async def test_search_handles_RequestError_from_search(make_SceneSearchJob, mocker):
    job = make_SceneSearchJob()
    cb = Mock()
    job.signal.register('search_results', cb)
    from_string_mock = mocker.patch('upsies.utils.scene.SceneQuery.from_string',
                                    return_value='mock query')
    search_mock = mocker.patch('upsies.utils.scene.search', AsyncMock(
        side_effect=errors.RequestError('no interwebs')))
    await job._search()
    assert from_string_mock.call_args_list == [call(job._content_path)]
    assert search_mock.call_args_list == [call('mock query')]
    assert job.output == ()
    assert job.errors == (errors.RequestError('no interwebs'),)
    assert job.exit_code == 1
    assert job.is_finished
    assert cb.call_args_list == []

@pytest.mark.asyncio
async def test_search_handles_no_results(make_SceneSearchJob, mocker):
    job = make_SceneSearchJob()
    cb = Mock()
    job.signal.register('search_results', cb)
    from_string_mock = mocker.patch('upsies.utils.scene.SceneQuery.from_string',
                                    return_value='mock query')
    search_mock = mocker.patch('upsies.utils.scene.search', AsyncMock(return_value=[]))
    await job._search()
    assert from_string_mock.call_args_list == [call(job._content_path)]
    assert search_mock.call_args_list == [call('mock query')]
    assert job.output == ()
    assert job.errors == ('No results',)
    assert job.exit_code == 1
    assert job.is_finished
    assert cb.call_args_list == [call([])]

@pytest.mark.asyncio
async def test_search_handles_results(make_SceneSearchJob, mocker):
    job = make_SceneSearchJob()
    cb = Mock()
    job.signal.register('search_results', cb)
    from_string_mock = mocker.patch('upsies.utils.scene.SceneQuery.from_string',
                                    return_value='mock query')
    search_mock = mocker.patch('upsies.utils.scene.search', AsyncMock(return_value=['foo', 'bar', 'baz']))
    await job._search()
    assert from_string_mock.call_args_list == [call(job._content_path)]
    assert search_mock.call_args_list == [call('mock query')]
    assert job.output == ('foo', 'bar', 'baz')
    assert job.errors == ()
    assert job.exit_code == 0
    assert job.is_finished
    assert cb.call_args_list == [call(['foo', 'bar', 'baz'])]
