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


@pytest.mark.asyncio
async def test_execute(make_SceneSearchJob, mocker):
    job = make_SceneSearchJob()
    mocker.patch.object(job, '_search', AsyncMock(return_value=['foo', 'bar', 'baz']))
    mocker.patch.object(job, '_handle_results')
    job.execute()
    await job._search_task
    assert job._search.call_args_list == [call()]
    assert job._handle_results.call_args_list == [call(job._search_task)]


@pytest.mark.parametrize(
    argnames='release_name, exp_args, exp_kwargs',
    argvalues=(
        ('Foo', ('Foo',), {}),
        ('Foo.1974', ('Foo', '1974'), {}),
        ('Foo 1974 1080p', ('Foo', '1974', '1080p'), {}),
        ('Foo.1974.1080p.BluRay', ('Foo', '1974', '1080p', 'BluRay'), {}),
        ('Foo 1080p BluRay x264', ('Foo', '1080p', 'BluRay', 'x264'), {}),
        ('Foo.1974.BluRay-ASDF', ('Foo', '1974', 'BluRay'), {'group': 'ASDF'}),
        ('Foo.S03.BluRay.x264', ('Foo', 'S03', 'BluRay', 'x264'), {}),
        ('Foo.S01E07.BluRay.x264', ('Foo', 'S01E07', 'BluRay', 'x264'), {}),
        ('Foo.S01E01E02.1080p.x264', ('Foo', 'S01E01E02', '1080p', 'x264'), {}),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_search_query(release_name, exp_args, exp_kwargs, make_SceneSearchJob, mocker):
    job = make_SceneSearchJob(content_path=release_name)
    mocker.patch.object(job._scenedb, 'search', AsyncMock())
    await job._search()
    assert job._scenedb.search.call_args_list == [
        call(*exp_args, **{**{'cache': True}, **exp_kwargs}),
    ]

@pytest.mark.parametrize('ignore_cache, exp_cache', ((True, False), (False, True)))
@pytest.mark.asyncio
async def test_search_cache_argument(ignore_cache, exp_cache, make_SceneSearchJob, mocker):
    job = make_SceneSearchJob(ignore_cache=ignore_cache, content_path='Foo')
    mocker.patch.object(job._scenedb, 'search', AsyncMock())
    await job._search()
    assert job._scenedb.search.call_args_list == [call('Foo', cache=exp_cache)]


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
