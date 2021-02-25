import asyncio
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies import errors
from upsies.jobs.submit import SubmitJob
from upsies.trackers import TrackerBase, TrackerConfigBase, TrackerJobsBase
from upsies.utils.btclients import ClientApiBase


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def job(tmp_path, tracker, tracker_jobs):
    return SubmitJob(
        home_directory=tmp_path,
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
        get_announce_url = AsyncMock()
        upload = AsyncMock()

    return TestTracker()

@pytest.fixture
def tracker_jobs(btclient, tracker):
    kwargs = {
        'content_path': 'content/path',
        'tracker': tracker,
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


def test_cache_id(job):
    assert job.cache_id == job._tracker.name


@pytest.mark.asyncio
async def test_initialize_creates_jobs_after_upload(tmp_path, tracker, tracker_jobs, mocker):
    logged = []

    def log(msg, return_value):
        logged.append(msg)
        return return_value

    type(tracker_jobs).jobs_after_upload = PropertyMock(
        side_effect=lambda: log('Creating jobs_after_upload', [Mock(), Mock()]),
    )
    SubmitJob(
        home_directory=tmp_path,
        ignore_cache=False,
        tracker=tracker,
        tracker_jobs=tracker_jobs,
    )
    assert logged == ['Creating jobs_after_upload']

@pytest.mark.asyncio
async def test_initialize_starts_jobs_after_upload_on_output(tmp_path, tracker, tracker_jobs, mocker):
    type(tracker_jobs).jobs_after_upload = PropertyMock(
        return_value=[Mock(), Mock(), Mock()],
    )
    job = SubmitJob(
        home_directory=tmp_path,
        ignore_cache=False,
        tracker=tracker,
        tracker_jobs=tracker_jobs,
    )
    assert len(job.jobs_after_upload) > 0
    for j in job.jobs_after_upload:
        assert j.start.call_args_list == []
    job.send('foo')
    for j in job.jobs_after_upload:
        assert j.start.call_args_list == [call()]


@pytest.mark.asyncio
async def test_wait_does_nothing_after_the_first_call(job, mocker):
    mocker.patch.object(job, '_run_jobs', AsyncMock())
    await job.wait()
    assert job.is_finished
    for _ in range(3):
        await job.wait()
    assert job._run_jobs.call_args_list == [call()]

@pytest.mark.asyncio
async def test_wait_is_called_multiple_times_simultaneously(job, mocker):
    calls = []

    async def _run_jobs():
        if calls:
            raise RuntimeError('I was already called')
        calls.append(call())
        await asyncio.sleep(0.1)

    mocker.patch.object(job, '_run_jobs', _run_jobs)

    await asyncio.gather(job.wait(), job.wait(), job.wait())
    assert job.is_finished
    assert calls == [call()]

@pytest.mark.asyncio
async def test_wait_is_cancelled_by_finish(job, mocker):
    mocker.patch.object(job, '_run_jobs', lambda: asyncio.sleep(100))
    asyncio.get_event_loop().call_soon(job.finish)
    await job.wait()
    assert job.is_finished

@pytest.mark.asyncio
async def test_wait_gets_unexpected_exception(job, mocker):
    mocker.patch.object(job, '_run_jobs', AsyncMock(side_effect=RuntimeError('asdf')))
    with pytest.raises(RuntimeError, match=r'^asdf$'):
        await job.wait()
    assert job.is_finished

@pytest.mark.asyncio
async def test_wait_does_everything_in_correct_order(job, mocker):
    mocks = AsyncMock()
    mocks.before1.configure_mock(start=Mock(), finish=Mock(), name='before1', output='before1 output', exit_code=0)
    mocks.before2.configure_mock(start=Mock(), finish=Mock(), name='before2', output='before2 output', exit_code=0)
    mocks.before3.configure_mock(start=Mock(), finish=Mock(), name='before3', output='before3 output', exit_code=0)
    mocks.after1.configure_mock(start=Mock(), finish=Mock(), name='after1', output='after1 output', exit_code=0)
    mocks.after2.configure_mock(start=Mock(), finish=Mock(), name='after1', output='after2 output', exit_code=0)
    mocker.patch.object(job, '_submit', mocks._submit)
    mocks._submit.side_effect = lambda *_, **__: job.send('mock torrent url')
    mocker.patch.object(job, 'jobs_before_upload', (mocks.before1, mocks.before2, mocks.before3))
    mocker.patch.object(job, 'jobs_after_upload', (mocks.after1, mocks.after2))
    await job.wait()
    assert job.is_finished
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
    assert len(mocks.mock_calls) == 6

@pytest.mark.parametrize('failed_job_number', (1, 2, 3))
@pytest.mark.asyncio
async def test_wait_doesnt_submit_nor_call_jobs_after_upload_if_job_before_upload_fails(failed_job_number, job, mocker):
    mocks = AsyncMock()
    mocks.before1.configure_mock(start=Mock(), finish=Mock(), name='before1', output='before1 output', exit_code=0)
    mocks.before2.configure_mock(start=Mock(), finish=Mock(), name='before2', output='before2 output', exit_code=0)
    mocks.before3.configure_mock(start=Mock(), finish=Mock(), name='before3', output='before3 output', exit_code=0)
    mocks.after1.configure_mock(start=Mock(), finish=Mock(), name='after1', output='after1 output', exit_code=0)
    mocks.after2.configure_mock(start=Mock(), finish=Mock(), name='after1', output='after2 output', exit_code=0)
    getattr(mocks, f'before{failed_job_number}').exit_code = 1
    mocker.patch.object(job, '_submit', mocks._submit)
    mocker.patch.object(job, 'jobs_before_upload', (mocks.before1, mocks.before2, mocks.before3))
    mocker.patch.object(job, 'jobs_after_upload', (mocks.after1, mocks.after2))
    await job.wait()
    assert job.is_finished
    for j in job.jobs_before_upload:
        j.finish.call_args_list == [call()]
    for j in job.jobs_after_upload:
        j.finish.call_args_list == [call()]
    assert job._submit.call_args_list == []
    assert set((str(call) for call in mocks.mock_calls)) == {
        str(call.before1.wait()),
        str(call.before2.wait()),
        str(call.before3.wait()),
    }

@pytest.mark.asyncio
async def test_wait_does_not_call_jobs_after_upload_if_submit_fails(job, mocker):
    mocks = AsyncMock()
    mocks.after1.configure_mock(start=Mock(), finish=Mock(), name='after1', output='after1 output', exit_code=0)
    mocks.after2.configure_mock(start=Mock(), finish=Mock(), name='after1', output='after2 output', exit_code=0)
    mocker.patch.object(job, '_submit', mocks._submit)  # Not sending output means failure
    mocker.patch.object(job, 'jobs_after_upload', (mocks.after1, mocks.after2))
    await job.wait()
    assert job.is_finished
    for j in job.jobs_after_upload:
        j.finish.call_args_list == [call()]
    assert mocks.mock_calls == [call._submit({})]


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
    if method in ('upload', 'logout'):
        assert job._tracker.logout.call_args_list == [call()]
    else:
        assert job._tracker.logout.call_args_list == []

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
        home_directory=tmp_path,
        ignore_cache=False,
        tracker=tracker,
        tracker_jobs=tracker_jobs,
    )
    assert getattr(job, attrname) == ('foo', 'bar')
