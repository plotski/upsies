import asyncio
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.jobs.submit import SubmitJob
from upsies.trackers import TrackerBase


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
def job(tmp_path, tracker):
    return SubmitJob(
        homedir=tmp_path,
        ignore_cache=False,
        tracker=tracker,
    )

@pytest.fixture
def tracker():
    class TestTracker(TrackerBase):
        name = 'test'
        label = 'TeST'
        jobs_before_upload = (
            Mock(wait=AsyncMock()),
            Mock(wait=AsyncMock()),
            Mock(wait=AsyncMock()),
        )
        login = AsyncMock()
        logout = AsyncMock()
        upload = AsyncMock()
    return TestTracker(config='mock config')


def test_cache_file(job):
    assert job.cache_file is None


@pytest.mark.asyncio
async def test_wait_finishes(job, mocker):
    mocker.patch.object(job, '_submit', AsyncMock())
    assert not job.is_finished
    await job.wait()
    assert job.is_finished

@pytest.mark.asyncio
async def test_wait_waits_for_jobs(job, mocker):
    mocker.patch.object(job, '_submit', AsyncMock())
    for subjob in job._tracker.jobs_before_upload:
        assert subjob.wait.call_args_list == []
    await job.wait()
    for subjob in job._tracker.jobs_before_upload:
        assert subjob.wait.call_args_list == [call()]

@pytest.mark.asyncio
async def test_wait_passes_job_output_to_submit(job, mocker):
    mocker.patch.object(job, '_submit', AsyncMock())
    for j, (name, output) in zip(job._tracker.jobs_before_upload,
                                 (('foo', ('a',)), ('bar', ('b1', 'b2')), ('baz', ('c',)))):
        j.configure_mock(name=name, output=output)
    await job.wait()
    assert job._submit.call_args_list == [
        call({'foo': ('a',), 'bar': ('b1', 'b2'), 'baz': ('c',)}),
    ]

@pytest.mark.asyncio
async def test_wait_does_nothing_after_the_first_call(job, mocker):
    mocker.patch.object(job, '_submit', AsyncMock())
    for j, (name, output) in zip(job._tracker.jobs_before_upload,
                                 (('foo', ('a',)), ('bar', ('b',)), ('baz', ('c',)))):
        j.configure_mock(name=name, output=output)
    assert not job.is_finished
    for _ in range(3):
        await job.wait()
        assert job.is_finished
    assert job._submit.call_args_list == [
        call({'foo': ('a',), 'bar': ('b',), 'baz': ('c',)}),
    ]

@pytest.mark.asyncio
async def test_wait_can_be_called_multiple_times_simultaneously(job, mocker):
    mocker.patch.object(job, '_submit', AsyncMock())

    for subjob, (name, output) in zip(job._tracker.jobs_before_upload,
                                      (('foo', 'a'), ('bar', 'b'), ('baz', 'c'))):
        subjob.configure_mock(name=name)

        async def set_output(subjob=subjob, output=output, calls=[1, 2, 3]):
            # Keep track of call index
            c = calls.pop(0)
            # Last subjob.wait() finishes first unless it is blocked by previous calls
            await asyncio.sleep(1 / c / 10)
            subjob.output = f'{c}: {output}'

        subjob.wait = set_output

    await asyncio.gather(job.wait(), job.wait(), job.wait())
    assert job._submit.call_args_list == [
        call({'foo': '1: a', 'bar': '1: b', 'baz': '1: c'}),
    ]


@pytest.mark.parametrize('method', ('login', 'logout', 'upload'))
@pytest.mark.asyncio
async def test_submit_handles_RequestError_from_tracker_coro(method, job):
    setattr(
        job._tracker,
        method,
        AsyncMock(side_effect=errors.RequestError(f'{method}: No connection')),
    )
    assert job.output == ()
    assert job.errors == ()
    await job._submit({})
    if method == 'logout':
        assert job.output == (str(job._tracker.upload.return_value),)
    else:
        assert job.output == ()
    assert job.errors == (errors.RequestError(f'{method}: No connection'),)

@pytest.mark.asyncio
async def test_submit_calls_methods_and_callbacks_in_correct_order(job, mocker):
    mocks = Mock()
    mocks.attach_mock(job._tracker.login, 'login')
    mocks.attach_mock(job._tracker.logout, 'logout')
    mocks.attach_mock(job._tracker.upload, 'upload')
    job.signal.register('logging_in', mocks.logging_in_cb)
    job.signal.register('logged_in', mocks.logged_in_cb)
    job.signal.register('uploading', mocks.uploading_cb)
    job.signal.register('uploaded', mocks.uploaded_cb)
    job.signal.register('logging_out', mocks.logging_out_cb)
    job.signal.register('logged_out', mocks.logged_out_cb)
    await job._submit({})
    assert mocks.method_calls == [
        call.logging_in_cb(),
        call.login(),
        call.logged_in_cb(),

        call.uploading_cb(),
        call.upload({}),
        call.uploaded_cb(),

        call.logging_out_cb(),
        call.logout(),
        call.logged_out_cb(),
    ]

@pytest.mark.asyncio
async def test_submit_sends_upload_return_value_as_output(job):
    job._tracker.upload.return_value = 'http://torrent.url/'
    await job._submit({})
    assert job.output == ('http://torrent.url/',)
