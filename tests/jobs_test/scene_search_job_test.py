from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.jobs.scene import SceneSearchJob
from upsies.utils import scene


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def scenedb():
    class TestSceneDbApi(scene.SceneDbApiBase):
        name = 'mocksy'
        label = 'Mocksy'
        _search = AsyncMock(return_value=[])

    return TestSceneDbApi()

@pytest.fixture
async def make_SceneSearchJob(tmp_path, scenedb):
    def make_SceneSearchJob(content_path=tmp_path, ignore_cache=False):
        return SceneSearchJob(
            home_directory=tmp_path,
            ignore_cache=ignore_cache,
            scenedb=scenedb,
            content_path=content_path,
        )
    return make_SceneSearchJob


def test_cache_id(make_SceneSearchJob):
    job = make_SceneSearchJob(content_path='path/to/Foo/')
    assert job.cache_id == (job._scenedb.name, 'Foo')


@pytest.mark.parametrize('ignore_cache, exp_cache', ((True, False), (False, True)))
@pytest.mark.asyncio
async def test_execute_cache_argument(ignore_cache, exp_cache, make_SceneSearchJob, mocker):
    job = make_SceneSearchJob(ignore_cache=ignore_cache)
    SceneQuery_mock = mocker.patch('upsies.utils.scene.SceneQuery')
    mocker.patch.object(job._scenedb, 'search', AsyncMock())
    mocker.patch.object(job, '_handle_results')
    job.execute()
    await job._search_task
    assert job._scenedb.search.call_args_list == [call(
        query=SceneQuery_mock.from_string.return_value,
        cache=exp_cache,
    )]
    assert job._handle_results.call_args_list == [call(job._search_task)]
    assert not job.is_finished

@pytest.mark.asyncio
async def test_execute_handles_SceneError(make_SceneSearchJob, mocker):
    job = make_SceneSearchJob()
    SceneQuery_mock = mocker.patch('upsies.utils.scene.SceneQuery.from_string',
                                   side_effect=errors.SceneError('no!'))
    mocker.patch.object(job._scenedb, 'search', AsyncMock())
    mocker.patch.object(job, '_handle_results')
    job.execute()
    assert not hasattr(job, '_search_task')
    assert job.errors == (errors.SceneError('no!'),)
    assert job.is_finished
    assert job._scenedb.search.call_args_list == []
    assert job._handle_results.call_args_list == []


@pytest.mark.parametrize('ignore_cache, exp_cache', ((True, False), (False, True)))
@pytest.mark.asyncio
async def test_search_cache_argument(ignore_cache, exp_cache, make_SceneSearchJob, mocker):
    job = make_SceneSearchJob(ignore_cache=ignore_cache, content_path='Foo')
    SceneQuery_mock = mocker.patch('upsies.utils.scene.SceneQuery')
    mocker.patch.object(job._scenedb, 'search', AsyncMock())
    job.execute()
    await job._search_task
    assert job._scenedb.search.call_args_list == [call(
        query=SceneQuery_mock.from_string.return_value,
        cache=exp_cache,
    )]


def test_handle_results_catches_SceneError(make_SceneSearchJob):
    job = make_SceneSearchJob()
    cb = Mock()
    job.signal.register('search_results', cb)
    task_mock = Mock(result=Mock(side_effect=errors.SceneError('no')))
    job._handle_results(task_mock)
    assert job.output == ()
    assert job.errors == (errors.SceneError('no'),)
    assert job.exit_code == 1
    assert job.is_finished
    assert cb.call_args_list == []

def test_handle_results_handles_no_results(make_SceneSearchJob):
    job = make_SceneSearchJob()
    cb = Mock()
    job.signal.register('search_results', cb)
    task_mock = Mock(result=Mock(return_value=[]))
    job._handle_results(task_mock)
    assert job.output == ()
    assert job.errors == ('No results',)
    assert job.exit_code == 1
    assert job.is_finished
    assert cb.call_args_list == [call([])]

def test_handle_results_handles_results(make_SceneSearchJob):
    job = make_SceneSearchJob()
    cb = Mock()
    job.signal.register('search_results', cb)
    task_mock = Mock(result=Mock(return_value=['foo', 'bar', 'baz']))
    job._handle_results(task_mock)
    assert job.output == ('foo', 'bar', 'baz')
    assert job.errors == ()
    assert job.exit_code == 0
    assert job.is_finished
    assert cb.call_args_list == [call(['foo', 'bar', 'baz'])]