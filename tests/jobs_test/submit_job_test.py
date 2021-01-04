import asyncio
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies import errors
from upsies.jobs.submit import SubmitJob
from upsies.trackers import TrackerBase, TrackerConfigBase, TrackerJobsBase
from upsies.utils.btclients import ClientApiBase


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
def job(tmp_path, tracker, tracker_jobs):
    return SubmitJob(
        homedir=tmp_path,
        ignore_cache=False,
        tracker=tracker,
        tracker_jobs=tracker_jobs,
    )

@pytest.fixture
def tracker():
    class TestTracker(TrackerBase):
        name = 'test'
        label = 'TeST'
        TrackerConfig = 'tracker config class'
        TrackerJobs = 'tracker jobs class'
        login = AsyncMock()
        logout = AsyncMock()
        upload = AsyncMock()

    return TestTracker()

@pytest.fixture
def tracker_jobs(btclient, tracker_config):
    kwargs = {
        'content_path': 'content/path',
        'tracker_name': 'tracker name',
        'tracker_config': tracker_config,
        'image_host': 'image host',
        'bittorrent_client': btclient,
        'torrent_destination': 'torrent/destination',
        'common_job_args': {},
    }

    class TestTrackerJobs(TrackerJobsBase):
        def __init__(self, **kw):
            return super().__init__(**{**kwargs, **kw})

        jobs_before_upload = PropertyMock()
        jobs_after_upload = PropertyMock()

    return TestTrackerJobs()

@pytest.fixture
def tracker_config():
    class TestTrackerConfig(TrackerConfigBase):
        defaults = {'username': 'foo', 'password': 'bar'}

    return TestTrackerConfig()

@pytest.fixture
def btclient():
    class TestClient(ClientApiBase):
        name = 'mock client'
        add_torrent = AsyncMock()

    return TestClient()


def test_cache_file(job):
    assert job.cache_file is None


@pytest.mark.asyncio
async def test_wait_can_be_called_multiple_times_simultaneously(job, mocker):
    mocker.patch.object(job, '_submit', AsyncMock())

    simultaneous_calls = 3
    jobs_before_upload = []
    jobs_after_upload = []
    for (name, output) in (('before1', 'a'), ('before2', 'b'), ('before3', 'c'),
                           ('after1', 'd'), ('after2', 'e')):
        subjob = Mock(exit_code=0)

        async def wait(subjob=subjob, output=output, call_indexes=list(range(1, simultaneous_calls + 1))):
            # Keep track of call index
            ci = call_indexes.pop(0)
            # Last subjob.wait() finishes first unless it is blocked by previous calls
            await asyncio.sleep(1 / ci / 10)
            subjob.configure_mock(output=f'call #{ci}: output={output}')

        subjob.configure_mock(name=name, wait=wait)
        if name.startswith('before'):
            jobs_before_upload.append(subjob)
        else:
            jobs_after_upload.append(subjob)

    mocker.patch.object(job, 'jobs_before_upload', jobs_before_upload)
    mocker.patch.object(job, 'jobs_after_upload', jobs_after_upload)

    coros = tuple(corofunc() for corofunc in [job.wait] * simultaneous_calls)
    await asyncio.gather(*coros)
    assert job._submit.call_args_list == [
        call({
            'before1': 'call #1: output=a',
            'before2': 'call #1: output=b',
            'before3': 'call #1: output=c',
        }),
    ]

@pytest.mark.asyncio
async def test_wait_does_nothing_after_the_first_call(job, mocker):
    mocks = AsyncMock()
    mocks.before1.configure_mock(start=Mock(), name='before1', output='before1 output', exit_code=0)
    mocks.before2.configure_mock(start=Mock(), name='before2', output='before2 output', exit_code=0)
    mocks.after1.configure_mock(start=Mock(), name='after1', output='after1 output', exit_code=0)
    mocks.after2.configure_mock(start=Mock(), name='after1', output='after2 output', exit_code=0)
    mocker.patch.object(job, '_submit', mocks._submit)
    mocker.patch.object(job, 'jobs_before_upload', (mocks.before1, mocks.before2))
    mocker.patch.object(job, 'jobs_after_upload', (mocks.after1, mocks.after2))
    assert not job.is_finished
    for _ in range(3):
        await job.wait()
        assert job.is_finished
    assert job._submit.call_args_list == [
        call({
            'before1': 'before1 output',
            'before2': 'before2 output',
        }),
    ]

@pytest.mark.asyncio
async def test_wait_creates_all_jobs_before_calling_submit(tmp_path, tracker, tracker_jobs, mocker):
    logged = []

    def log(msg, return_value):
        logged.append(msg)
        return return_value

    mocker.patch('upsies.jobs.submit.SubmitJob._submit',
                 side_effect=lambda *_, **__: log('Calling _submit', AsyncMock()))
    type(tracker_jobs).jobs_before_upload = PropertyMock(
        side_effect=lambda *_, **__: log('Instantiating jobs before upload',
                                         [Mock(wait=AsyncMock(), exit_code=0),
                                          Mock(wait=AsyncMock(), exit_code=0)]),
    )
    type(tracker_jobs).jobs_after_upload = PropertyMock(
        side_effect=lambda *_, **__: log('Instantiating jobs after upload',
                                         [Mock(wait=AsyncMock(), exit_code=0),
                                          Mock(wait=AsyncMock(), exit_code=0)]),
    )
    job = SubmitJob(
        homedir=tmp_path,
        ignore_cache=False,
        tracker=tracker,
        tracker_jobs=tracker_jobs,
    )
    await job.wait()
    assert logged[-1] == 'Calling _submit'

@pytest.mark.asyncio
async def test_wait_does_everything_in_correct_order(job, mocker):
    mocks = AsyncMock()
    mocks.before1.configure_mock(start=Mock(), name='before1', output='before1 output', exit_code=0)
    mocks.before2.configure_mock(start=Mock(), name='before2', output='before2 output', exit_code=0)
    mocks.before3.configure_mock(start=Mock(), name='before3', output='before3 output', exit_code=0)
    mocks.after1.configure_mock(start=Mock(), name='after1', output='after1 output', exit_code=0)
    mocks.after2.configure_mock(start=Mock(), name='after1', output='after2 output', exit_code=0)
    mocker.patch.object(job, '_submit', mocks._submit)
    mocks._submit.side_effect = lambda *_, **__: job.send('mock torrent url')
    mocker.patch.object(job, 'jobs_before_upload', (mocks.before1, mocks.before2, mocks.before3))
    mocker.patch.object(job, 'jobs_after_upload', (mocks.after1, mocks.after2))
    await job.wait()
    # Order of before* and after* jobs doesn't matter and is random for Python <
    # 3.8. Compare str(call()) because call() isn't hashable and sets can only
    # contain hashable values.
    assert set((str(call) for call in mocks.mock_calls[:3])) == {
        str(call.before1.wait()),
        str(call.before2.wait()),
        str(call.before3.wait()),
    }
    assert mocks.mock_calls[3] == call._submit({
        'before1': 'before1 output',
        'before2': 'before2 output',
        'before3': 'before3 output',
    })
    assert set((str(call) for call in mocks.mock_calls[4:6])) == {
        str(call.after1.start()),
        str(call.after2.start()),
    }
    assert set((str(call) for call in mocks.mock_calls[6:8])) == {
        str(call.after1.wait()),
        str(call.after2.wait()),
    }

@pytest.mark.parametrize('failed_job_number', (1, 2, 3))
@pytest.mark.asyncio
async def test_wait_does_not_submit_if_any_jobs_before_upload_fail(failed_job_number, job, mocker):
    mocks = AsyncMock()
    mocks.before1.configure_mock(start=Mock(), name='before1', output='before1 output', exit_code=0)
    mocks.before2.configure_mock(start=Mock(), name='before2', output='before2 output', exit_code=0)
    mocks.before3.configure_mock(start=Mock(), name='before3', output='before3 output', exit_code=0)
    mocks.after1.configure_mock(start=Mock(), name='after1', output='after1 output', exit_code=0)
    mocks.after2.configure_mock(start=Mock(), name='after1', output='after2 output', exit_code=0)
    getattr(mocks, f'before{failed_job_number}').exit_code = 1
    mocker.patch.object(job, '_submit', mocks._submit)
    mocker.patch.object(job, 'jobs_before_upload', (mocks.before1, mocks.before2, mocks.before3))
    mocker.patch.object(job, 'jobs_after_upload', (mocks.after1, mocks.after2))
    await job.wait()
    assert job._submit.call_args_list == []
    assert set((str(call) for call in mocks.mock_calls)) == {
        str(call.before1.wait()),
        str(call.before2.wait()),
        str(call.before3.wait()),
    }
    assert job.is_finished

@pytest.mark.asyncio
async def test_wait_does_not_call_jobs_after_upload_if_submit_fails(job, mocker):
    mocks = AsyncMock()
    mocks.after1.configure_mock(start=Mock(), name='after1', output='after1 output', exit_code=0)
    mocks.after2.configure_mock(start=Mock(), name='after1', output='after2 output', exit_code=0)
    mocker.patch.object(job, '_submit', mocks._submit)
    mocker.patch.object(job, 'jobs_after_upload', (mocks.after1, mocks.after2))
    await job.wait()
    assert mocks.mock_calls == [call._submit({})]
    assert job.is_finished

@pytest.mark.asyncio
async def test_wait_finishes(job, mocker):
    mocker.patch.object(job, '_submit', AsyncMock())
    mocker.patch.object(job, 'jobs_before_upload', ())
    mocker.patch.object(job, 'jobs_after_upload', ())
    assert not job.is_finished
    await job.wait()
    assert job.is_finished


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

@pytest.mark.asyncio
async def test_submit_sets_info_property_to_current_status(job):
    infos = [
        'Logging in',
        'Logged in',
        'Uploading',
        'Uploaded',
        'Logging out',
        '',
    ]
    def info_cb():
        assert job.info == infos.pop(0)
    job.signal.register('logging_in', info_cb)
    job.signal.register('logged_in', info_cb)
    job.signal.register('uploading', info_cb)
    job.signal.register('uploaded', info_cb)
    job.signal.register('logging_out', info_cb)
    job.signal.register('logged_out', info_cb)
    await job._submit({})
    assert infos == []


@pytest.mark.parametrize('attrname', ('jobs_before_upload', 'jobs_after_upload'))
@pytest.mark.asyncio
async def test_None_is_filtered_from_jobs(attrname, tmp_path, tracker, tracker_jobs, mocker):
    mocker.patch('upsies.jobs.submit.SubmitJob._submit')
    setattr(
        type(tracker_jobs),
        attrname,
        PropertyMock(return_value=[None, 'foo', None, 'bar']),
    )
    job = SubmitJob(
        homedir=tmp_path,
        ignore_cache=False,
        tracker=tracker,
        tracker_jobs=tracker_jobs,
    )
    assert getattr(job, attrname) == ('foo', 'bar')
