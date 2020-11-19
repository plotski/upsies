import asyncio
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.jobs.submit import SubmitJob


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
    return Mock(
        jobs_before_upload=(
            Mock(wait=AsyncMock()),
            Mock(wait=AsyncMock()),
            Mock(wait=AsyncMock()),
        ),
        login=AsyncMock(),
        logout=AsyncMock(),
        upload=AsyncMock(),
    )


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
    mocker.patch.object(job, '_call_callbacks', mocks._call_callbacks)
    await job._submit({})
    assert mocks.method_calls == [
        call._call_callbacks(job.signal.logging_in),
        call.login(),
        call._call_callbacks(job.signal.logged_in),

        call._call_callbacks(job.signal.uploading),
        call.upload({}),
        call._call_callbacks(job.signal.uploaded),

        call._call_callbacks(job.signal.logging_out),
        call.logout(),
        call._call_callbacks(job.signal.logged_out),
    ]

@pytest.mark.asyncio
async def test_submit_sends_upload_return_value_as_output(job):
    job._tracker.upload.return_value = 'http://torrent.url/'
    await job._submit({})
    assert job.output == ('http://torrent.url/',)


@pytest.mark.parametrize('signal', SubmitJob.signal, ids=lambda v: v.name)
def test_callback_with_valid_signal(signal, job):
    cb = Mock()
    job.on(signal, cb)
    job._call_callbacks(signal)
    assert cb.call_args_list == [call()]
    job._call_callbacks(signal)
    assert cb.call_args_list == [call(), call()]

@pytest.mark.parametrize('signal', SubmitJob.signal, ids=lambda v: v.name)
def test_callback_with_invalid_signal(signal, job):
    cb = Mock()
    with pytest.raises(RuntimeError, match=r"^Unknown signal: 'foo'$"):
        job.on('foo', cb)
    job._call_callbacks(signal)
    assert cb.call_args_list == []
