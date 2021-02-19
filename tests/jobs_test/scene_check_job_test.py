import asyncio
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.jobs.scene import SceneCheckJob
from upsies.utils.scene import SceneQuery
from upsies.utils.types import SceneCheckResult


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
async def make_SceneCheckJob(tmp_path):
    def make_SceneCheckJob(content_path=tmp_path, ignore_cache=False):
        return SceneCheckJob(
            home_directory=tmp_path,
            ignore_cache=ignore_cache,
            content_path=content_path,
        )
    return make_SceneCheckJob


def test_cache_id(make_SceneCheckJob):
    job = make_SceneCheckJob(content_path='path/to/Foo/')
    assert job.cache_id == ('Foo',)


@pytest.mark.parametrize(
    argnames='exc, msg, exp_exc, exp_msg',
    argvalues=(
        (None, None, None, None),
        (errors.RequestError, 'Foo', None, None),
        (errors.SceneError, 'Foo', None, None),
        (TypeError, 'Foo', TypeError, 'Foo'),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_catch_errors(exc, msg, exp_exc, exp_msg, make_SceneCheckJob, mocker):
    async def coro():
        if exc:
            raise exc(msg)

    job = make_SceneCheckJob()
    await job._catch_errors(coro())

    if exp_exc:
        asyncio.get_event_loop().call_soon(job.finish)
        with pytest.raises(exp_exc, match=rf'^{exp_msg}$'):
            await job.wait()
    else:
        if not exc:
            asyncio.get_event_loop().call_soon(job.finish)
        await job.wait()
        assert job.errors == ((exc(msg),) if exc else ())
        assert job.is_finished


@pytest.mark.asyncio
async def test_execute(make_SceneCheckJob, mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob._find_release_name', AsyncMock())
    job = make_SceneCheckJob()
    job.execute()
    asyncio.get_event_loop().call_soon(job.finish)
    await job.wait()
    assert job._find_release_name.call_args_list == [call()]


@pytest.mark.asyncio
async def test_find_release_name_gets_nonscene_release(make_SceneCheckJob, mocker):
    is_scene_release_mock = mocker.patch('upsies.utils.scene.is_scene_release', AsyncMock(
        return_value=SceneCheckResult.false,
    ))
    mocker.patch('upsies.jobs.scene.SceneCheckJob._finalize')
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    ask_release_name = Mock()
    job = make_SceneCheckJob(content_path='path/to/foo')
    job.signal.register('ask_release_name', ask_release_name)
    await job._find_release_name()
    assert is_scene_release_mock.call_args_list == [call('path/to/foo')]
    assert ask_release_name.call_args_list == []
    assert job._finalize.call_args_list == [
        call(SceneCheckResult.false, exceptions=()),
    ]
    assert job._verify_release.call_args_list == []

@pytest.mark.parametrize('is_scene_release', (SceneCheckResult.true, SceneCheckResult.unknown))
@pytest.mark.asyncio
async def test_find_release_name_finds_no_results(is_scene_release, make_SceneCheckJob, mocker):
    is_scene_release_mock = mocker.patch('upsies.utils.scene.is_scene_release', AsyncMock(
        return_value=is_scene_release,
    ))
    search_mock = mocker.patch('upsies.utils.scene.search', AsyncMock(
        return_value=(),
    ))
    mocker.patch('upsies.jobs.scene.SceneCheckJob._finalize')
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    ask_release_name = Mock()
    job = make_SceneCheckJob(content_path='path/to/foo')
    job.signal.register('ask_release_name', ask_release_name)
    await job._find_release_name()
    assert is_scene_release_mock.call_args_list == [call('path/to/foo')]
    assert search_mock.call_args_list == [call(SceneQuery('foo'))]
    assert ask_release_name.call_args_list == []
    assert job._finalize.call_args_list == [
        call(SceneCheckResult.unknown, exceptions=()),
    ]
    assert job._verify_release.call_args_list == []

@pytest.mark.parametrize('is_scene_release', (SceneCheckResult.true, SceneCheckResult.unknown))
@pytest.mark.asyncio
async def test_find_release_name_finds_single_result(is_scene_release, make_SceneCheckJob, mocker):
    is_scene_release_mock = mocker.patch('upsies.utils.scene.is_scene_release', AsyncMock(
        return_value=is_scene_release,
    ))
    search_mock = mocker.patch('upsies.utils.scene.search', AsyncMock(
        return_value=('Mock.Release.Foo-BAR',),
    ))
    mocker.patch('upsies.jobs.scene.SceneCheckJob._finalize')
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    ask_release_name = Mock()
    job = make_SceneCheckJob(content_path='path/to/foo')
    job.signal.register('ask_release_name', ask_release_name)
    await job._find_release_name()
    assert is_scene_release_mock.call_args_list == [call('path/to/foo')]
    assert search_mock.call_args_list == [call(SceneQuery('foo'))]
    assert ask_release_name.call_args_list == []
    assert job._finalize.call_args_list == []
    assert job._verify_release.call_args_list == [
        call('Mock.Release.Foo-BAR'),
    ]

@pytest.mark.parametrize('is_scene_release', (SceneCheckResult.true, SceneCheckResult.unknown))
@pytest.mark.asyncio
async def test_find_release_name_finds_parsed_release_name_in_result(is_scene_release, make_SceneCheckJob, mocker):
    is_scene_release_mock = mocker.patch('upsies.utils.scene.is_scene_release', AsyncMock(
        return_value=is_scene_release,
    ))
    search_mock = mocker.patch('upsies.utils.scene.search', AsyncMock(
        return_value=('foo', 'bar', 'baz'),
    ))
    mocker.patch('upsies.jobs.scene.SceneCheckJob._finalize')
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    ask_release_name = Mock()
    job = make_SceneCheckJob(content_path='path/to/foo')
    job.signal.register('ask_release_name', ask_release_name)
    await job._find_release_name()
    assert is_scene_release_mock.call_args_list == [call('path/to/foo')]
    assert search_mock.call_args_list == [call(SceneQuery('foo'))]
    assert ask_release_name.call_args_list == []
    assert job._finalize.call_args_list == []
    assert job._verify_release.call_args_list == [
        call('foo'),
    ]

@pytest.mark.parametrize('is_scene_release', (SceneCheckResult.true, SceneCheckResult.unknown))
@pytest.mark.asyncio
async def test_find_release_name_finds_multiple_results(is_scene_release, make_SceneCheckJob, mocker):
    is_scene_release_mock = mocker.patch('upsies.utils.scene.is_scene_release', AsyncMock(
        return_value=is_scene_release,
    ))
    search_mock = mocker.patch('upsies.utils.scene.search', AsyncMock(
        return_value=('Mock.Release.Foo-BAR', 'Mick.Release.Foo-BAR'),
    ))
    mocker.patch('upsies.jobs.scene.SceneCheckJob._finalize')
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    ask_release_name = Mock()
    job = make_SceneCheckJob(content_path='path/to/foo')
    job.signal.register('ask_release_name', ask_release_name)
    await job._find_release_name()
    assert is_scene_release_mock.call_args_list == [call('path/to/foo')]
    assert search_mock.call_args_list == [call(SceneQuery('foo'))]
    assert ask_release_name.call_args_list == [
        call(('Mock.Release.Foo-BAR', 'Mick.Release.Foo-BAR')),
    ]
    assert job._finalize.call_args_list == []
    assert job._verify_release.call_args_list == []


@pytest.mark.asyncio
async def test_user_selected_release_name(make_SceneCheckJob, mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    job = make_SceneCheckJob()
    job.user_selected_release_name('mock.release.name')
    asyncio.get_event_loop().call_soon(job.finish)
    await job.wait()
    assert job._verify_release.call_args_list == [call('mock.release.name')]


@pytest.mark.asyncio
async def test_verify_release(make_SceneCheckJob, mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob._finalize')
    verify_release_mock = mocker.patch('upsies.utils.scene.verify_release', AsyncMock(
        return_value=(SceneCheckResult.true, ('error1', 'error2')),
    ))
    job = make_SceneCheckJob()
    await job._verify_release('mock.release.name')
    assert verify_release_mock.call_args_list == [
        call(job._content_path, 'mock.release.name'),
    ]
    assert job._finalize.call_args_list == [
        call(SceneCheckResult.true, ('error1', 'error2')),
    ]


def test_finalize_ignores_SceneMissingFileError(make_SceneCheckJob, mocker):
    ask_is_scene_release = Mock()
    job = make_SceneCheckJob()
    job.signal.register('ask_is_scene_release', ask_is_scene_release)
    job._finalize(
        'mock scene check result',
        (
            errors.SceneError('foo'),
            errors.SceneMissingFileError('bar'),
            errors.SceneFileSizeError('baz', 123, 456),
            errors.SceneMissingFileError('bam'),
        ),
    )
    assert job.errors == (
        errors.SceneError('foo'),
        errors.SceneFileSizeError('baz', 123, 456),
    )
    assert ask_is_scene_release.call_args_list == []
    assert job.is_finished

def test_finalize_triggers_dialog_if_no_errors(make_SceneCheckJob, mocker):
    ask_is_scene_release = Mock()
    job = make_SceneCheckJob()
    job.signal.register('ask_is_scene_release', ask_is_scene_release)
    job._finalize('mock scene check result', ())
    assert job.errors == ()
    assert ask_is_scene_release.call_args_list == [
        call('mock scene check result'),
    ]
    assert not job.is_finished

@pytest.mark.parametrize(
    argnames='is_scene_release, exp_msg',
    argvalues=(
        (SceneCheckResult.true, 'Scene release'),
        (SceneCheckResult.false, 'Not a scene release'),
        (SceneCheckResult.unknown, 'May be a scene release'),
    ),
    ids=lambda v: str(v),
)
def test_user_decided(is_scene_release, exp_msg, make_SceneCheckJob, mocker):
    job = make_SceneCheckJob()
    job.user_decided(is_scene_release)
    assert job.output == (exp_msg,)
    assert job.is_finished
