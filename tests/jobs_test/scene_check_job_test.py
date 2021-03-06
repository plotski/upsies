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
def make_SceneCheckJob(tmp_path):
    def make_SceneCheckJob(content_path=tmp_path, ignore_cache=False):
        return SceneCheckJob(
            home_directory=tmp_path,
            cache_directory=tmp_path,
            ignore_cache=ignore_cache,
            content_path=content_path,
        )
    return make_SceneCheckJob


def test_cache_id(make_SceneCheckJob):
    job = make_SceneCheckJob(content_path='path/to/Foo/')
    assert job.cache_id == 'Foo'


@pytest.mark.parametrize(
    argnames='exc, msg, exp_exc, exp_msg',
    argvalues=(
        (None, None, None, None),
        (errors.SceneError, 'Foo', None, None),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_catch_errors_reports_SceneError(exc, msg, exp_exc, exp_msg, make_SceneCheckJob, mocker):
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
async def test_catch_errors_warns_about_RequestError(make_SceneCheckJob, mocker):
    async def coro():
        raise errors.RequestError('teh interwebs borked!')

    job = make_SceneCheckJob()
    ask_is_scene_release_cb = Mock()
    job.signal.register('ask_is_scene_release', ask_is_scene_release_cb)
    await job._catch_errors(coro())
    assert job.warnings == ('teh interwebs borked!',)
    assert job.errors == ()
    assert not job.is_finished


@pytest.mark.asyncio
async def test_execute(make_SceneCheckJob, mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob._find_release_name', AsyncMock())
    job = make_SceneCheckJob()
    job.execute()
    await job.await_tasks()
    assert job._find_release_name.call_args_list == [call()]


@pytest.mark.asyncio
async def test_find_release_name_gets_nonscene_release(make_SceneCheckJob, mocker):
    is_scene_release_mock = mocker.patch('upsies.utils.scene.is_scene_release', AsyncMock(
        return_value=SceneCheckResult.false,
    ))
    mocker.patch('upsies.jobs.scene.SceneCheckJob._handle_scene_check_result')
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    ask_release_name = Mock()
    job = make_SceneCheckJob(content_path='path/to/foo')
    job.signal.register('ask_release_name', ask_release_name)
    await job._find_release_name()
    assert is_scene_release_mock.call_args_list == [call('path/to/foo')]
    assert ask_release_name.call_args_list == []
    assert job._handle_scene_check_result.call_args_list == [call(SceneCheckResult.false)]
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
    mocker.patch('upsies.jobs.scene.SceneCheckJob._handle_scene_check_result')
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    ask_release_name = Mock()
    job = make_SceneCheckJob(content_path='path/to/foo')
    job.signal.register('ask_release_name', ask_release_name)
    await job._find_release_name()
    assert is_scene_release_mock.call_args_list == [call('path/to/foo')]
    assert search_mock.call_args_list == [call(SceneQuery('foo'), only_existing_releases=False)]
    assert ask_release_name.call_args_list == []
    assert job._handle_scene_check_result.call_args_list == [call(SceneCheckResult.unknown)]
    assert job._verify_release.call_args_list == []

@pytest.mark.parametrize(
    argnames='search_result, is_scene_release, exp_ask_release_name_calls, exp_verify_release_calls',
    argvalues=(
        ('Mock.Release.Foo-BAR', SceneCheckResult.true, [], [call('Mock.Release.Foo-BAR')]),
        ('Mock.Release.Foo-BAR', SceneCheckResult.unknown, [call(('Mock.Release.Foo-BAR',))], []),
    ),
)
@pytest.mark.asyncio
async def test_find_release_name_finds_single_result(search_result, is_scene_release, exp_ask_release_name_calls, exp_verify_release_calls, make_SceneCheckJob, mocker):
    is_scene_release_mock = mocker.patch('upsies.utils.scene.is_scene_release', AsyncMock(
        return_value=is_scene_release,
    ))
    search_mock = mocker.patch('upsies.utils.scene.search', AsyncMock(
        return_value=(search_result,),
    ))
    mocker.patch('upsies.jobs.scene.SceneCheckJob._handle_scene_check_result')
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    ask_release_name = Mock()
    job = make_SceneCheckJob(content_path='path/to/foo')
    job.signal.register('ask_release_name', ask_release_name)
    await job._find_release_name()
    assert is_scene_release_mock.call_args_list == [call('path/to/foo')]
    assert search_mock.call_args_list == [call(SceneQuery('foo'), only_existing_releases=False)]
    assert job._handle_scene_check_result.call_args_list == []
    assert ask_release_name.call_args_list == exp_ask_release_name_calls
    assert job._verify_release.call_args_list == exp_verify_release_calls

@pytest.mark.parametrize('is_scene_release', (SceneCheckResult.true, SceneCheckResult.unknown))
@pytest.mark.asyncio
async def test_find_release_name_finds_parsed_release_name_in_result(is_scene_release, make_SceneCheckJob, mocker):
    is_scene_release_mock = mocker.patch('upsies.utils.scene.is_scene_release', AsyncMock(
        return_value=is_scene_release,
    ))
    search_mock = mocker.patch('upsies.utils.scene.search', AsyncMock(
        return_value=('foo', 'bar', 'baz'),
    ))
    mocker.patch('upsies.jobs.scene.SceneCheckJob._handle_scene_check_result')
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    ask_release_name = Mock()
    job = make_SceneCheckJob(content_path='path/to/foo')
    job.signal.register('ask_release_name', ask_release_name)
    await job._find_release_name()
    assert is_scene_release_mock.call_args_list == [call('path/to/foo')]
    assert search_mock.call_args_list == [call(SceneQuery('foo'), only_existing_releases=False)]
    assert ask_release_name.call_args_list == []
    assert job._handle_scene_check_result.call_args_list == []
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
    mocker.patch('upsies.jobs.scene.SceneCheckJob._handle_scene_check_result')
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    ask_release_name = Mock()
    job = make_SceneCheckJob(content_path='path/to/foo')
    job.signal.register('ask_release_name', ask_release_name)
    await job._find_release_name()
    assert is_scene_release_mock.call_args_list == [call('path/to/foo')]
    assert search_mock.call_args_list == [call(SceneQuery('foo'), only_existing_releases=False)]
    assert ask_release_name.call_args_list == [
        call(('Mock.Release.Foo-BAR', 'Mick.Release.Foo-BAR')),
    ]
    assert job._handle_scene_check_result.call_args_list == []
    assert job._verify_release.call_args_list == []


@pytest.mark.asyncio
async def test_user_selected_release_name_with_release_name(make_SceneCheckJob, mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    mocker.patch('upsies.jobs.scene.SceneCheckJob._handle_scene_check_result', Mock())
    job = make_SceneCheckJob()
    job.user_selected_release_name('mock.release.name')
    await job.await_tasks()
    assert job._verify_release.call_args_list == [call('mock.release.name')]
    assert job._handle_scene_check_result.call_args_list == []

@pytest.mark.asyncio
async def test_user_selected_release_name_without_release_name(make_SceneCheckJob, mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob._verify_release', AsyncMock())
    mocker.patch('upsies.jobs.scene.SceneCheckJob._handle_scene_check_result', Mock())
    job = make_SceneCheckJob()
    job.user_selected_release_name(None)
    await job.await_tasks()
    assert job._verify_release.call_args_list == []
    assert job._handle_scene_check_result.call_args_list == [call(SceneCheckResult.false)]


@pytest.mark.asyncio
async def test_verify_release(make_SceneCheckJob, mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob._handle_scene_check_result')
    verify_release_mock = mocker.patch('upsies.utils.scene.verify_release', AsyncMock(
        return_value=(SceneCheckResult.true, ('error1', 'error2')),
    ))
    job = make_SceneCheckJob()
    await job._verify_release('mock.release.name')
    assert verify_release_mock.call_args_list == [
        call(job._content_path, 'mock.release.name'),
    ]
    assert job._handle_scene_check_result.call_args_list == [
        call(SceneCheckResult.true, ('error1', 'error2')),
    ]


def test_handle_scene_check_result_handles_SceneErrors(make_SceneCheckJob, mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob.finalize')
    ask_is_scene_release = Mock()
    job = make_SceneCheckJob()
    job.signal.register('ask_is_scene_release', ask_is_scene_release)
    job._handle_scene_check_result(
        'mock scene check result',
        exceptions=(
            errors.SceneError('foo'),
            errors.SceneRenamedError(original_name='bar', existing_name='Bar'),
            errors.SceneMissingInfoError('burr'),
            errors.SceneFileSizeError('baz', original_size=123, existing_size=456),
        ),
    )
    assert job.warnings == (str(errors.SceneMissingInfoError('burr')),)
    assert job.errors == (errors.SceneError('foo'),)
    assert ask_is_scene_release.call_args_list == []
    assert job.finalize.call_args_list == []
    assert job.is_finished

@pytest.mark.parametrize('is_scene_release', (SceneCheckResult.true, SceneCheckResult.false))
def test_handle_scene_check_result_handles_definite_scene_check_result(is_scene_release, make_SceneCheckJob, mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob.finalize')
    ask_is_scene_release = Mock()
    job = make_SceneCheckJob()
    job.signal.register('ask_is_scene_release', ask_is_scene_release)
    job._handle_scene_check_result(is_scene_release, exceptions=())
    assert job.errors == ()
    assert job.warnings == ()
    assert ask_is_scene_release.call_args_list == []
    assert job.finalize.call_args_list == [call(is_scene_release)]
    assert not job.is_finished

@pytest.mark.parametrize('is_scene_release', (SceneCheckResult.unknown,))
def test_handle_scene_check_result_triggers_dialog_if_no_errors(is_scene_release, make_SceneCheckJob, mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob.finalize')
    ask_is_scene_release = Mock()
    job = make_SceneCheckJob()
    job.signal.register('ask_is_scene_release', ask_is_scene_release)
    job._handle_scene_check_result('mock scene check result', ())
    assert job.errors == ()
    assert job.warnings == ()
    assert ask_is_scene_release.call_args_list == [
        call('mock scene check result'),
    ]
    assert job.finalize.call_args_list == []
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
def test_finalize(is_scene_release, exp_msg, make_SceneCheckJob, mocker):
    cb = Mock()
    job = make_SceneCheckJob()
    job.signal.register('checked', cb)
    assert job.is_scene_release is None
    job.finalize(is_scene_release)
    assert job.output == (exp_msg,)
    assert cb.call_args_list == [call(is_scene_release)]
    assert job.is_scene_release is is_scene_release
    assert job.is_finished


@pytest.mark.parametrize(
    argnames='is_scene_release',
    argvalues=(
        SceneCheckResult.true,
        SceneCheckResult.false,
        SceneCheckResult.unknown,
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_is_scene_release_property_is_replayed_from_cache(is_scene_release, make_SceneCheckJob, mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob._find_release_name', AsyncMock())
    job = make_SceneCheckJob(ignore_cache=False)
    assert job.is_scene_release is None
    job.start()
    await job.await_tasks()
    job.finalize(is_scene_release)  # Cache is_scene_release
    assert job.is_scene_release is is_scene_release

    for _ in range(3):
        job = make_SceneCheckJob(ignore_cache=False)
        job.start()  # Load is_scene_release from cache
        assert job.is_scene_release is is_scene_release
