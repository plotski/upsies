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
        cache_directory=tmp_path,
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
        is_logged_in = PropertyMock()
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
        submission_ok = PropertyMock(return_value=True)

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
        cache_directory=tmp_path,
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
        cache_directory=tmp_path,
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


def test_execute_adds_run_jobs_task(job, mocker):
    mocker.patch.object(job, 'add_task')
    mocker.patch.object(job, '_run_jobs', Mock())
    assert job.add_task.call_args_list == []
    job.execute()
    assert job.add_task.call_args_list == [call(job._run_jobs.return_value)]
    assert job._run_jobs.call_args_list == [call()]

def test_execute_does_nothing_if_job_is_finished_task(job, mocker):
    mocker.patch.object(job, 'add_task')
    mocker.patch.object(job, '_run_jobs')
    assert job.add_task.call_args_list == []
    job.finish()
    job.execute()
    assert job.add_task.call_args_list == []


@pytest.mark.asyncio
async def test_run_jobs_waits_for_jobs_until_all_are_finished(job, mocker):
    class MockJob:
        def __init__(self, name, is_finished_values):
            self.name = name
            self.exit_code = 0
            self._is_finished_values = list(is_finished_values)
            self._is_finished = self._is_finished_values.pop(0)
            self.wait_calls = 0

        async def wait(self):
            if self._is_finished_values:
                self.wait_calls += 1
                self._is_finished = self._is_finished_values.pop(0)

        @property
        def is_finished(self):
            return self._is_finished

    jobs = {
        'a': MockJob('a', (False, False, True)),
        'b': MockJob('b', (False, True)),
        'c': MockJob('c', (False, False, False, True)),
    }
    mocker.patch.object(type(job), 'jobs_before_upload', PropertyMock(side_effect=(
        (jobs['a'],),
        (jobs['a'], jobs['b']),
        (jobs['a'], jobs['b'], jobs['c']),
        (jobs['a'], jobs['b'], jobs['c']),
        (jobs['a'], jobs['b'], jobs['c']),
        (jobs['a'], jobs['b'], jobs['c']),
    )))
    await job._run_jobs()
    assert jobs['a'].wait_calls == 2
    assert jobs['b'].wait_calls == 1
    assert jobs['c'].wait_calls == 3

@pytest.mark.parametrize('submission_ok, exp_calls', ((True, [call()]), (False, [])))
@pytest.mark.asyncio
async def test_run_jobs_submits_if_submission_ok(submission_ok, exp_calls, job, mocker):
    mocker.patch.object(job, '_submit', AsyncMock())
    mocker.patch.object(type(job._tracker_jobs), 'submission_ok', PropertyMock(return_value=submission_ok))
    assert not job.is_finished
    await job._run_jobs()
    assert job._submit.call_args_list == exp_calls
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
    await job._submit()
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
    await job._submit()
    assert mocks.method_calls == [
        call.logging_in_cb(),
        call.login(),
        call.logged_in_cb(),

        call.uploading_cb(),
        call.upload(job._tracker_jobs),
        call.uploaded_cb(),

        call.logging_out_cb(),
        call.logout(),
        call.logged_out_cb(),
    ]

@pytest.mark.asyncio
async def test_submit_sends_upload_return_value_as_output(job):
    job._tracker.upload.return_value = 'http://torrent.url/'
    await job._submit()
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
    await job._submit()
    assert infos == []


@pytest.mark.parametrize('attrname', ('jobs_before_upload', 'jobs_after_upload'))
@pytest.mark.asyncio
async def test_None_and_disabled_are_filtered_from_jobs_attributes(attrname, tmp_path, tracker, tracker_jobs, mocker):
    foo_job = Mock(name='foo', is_enabled=True)
    bar_job = Mock(name='bar', is_enabled=False)
    baz_job = Mock(name='baz', is_enabled=True)
    mocker.patch('upsies.jobs.submit.SubmitJob._submit')
    setattr(
        type(tracker_jobs),
        attrname,
        PropertyMock(return_value=[foo_job, None, bar_job, None, baz_job]),
    )
    job = SubmitJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=False,
        tracker=tracker,
        tracker_jobs=tracker_jobs,
    )
    assert getattr(job, attrname) == (foo_job, baz_job)


@pytest.mark.parametrize('submission_ok, exp_hidden', ((False, True), (True, False)))
def test_hidden_property(submission_ok, exp_hidden, job, mocker):
    mocker.patch.object(type(job._tracker_jobs), 'submission_ok', PropertyMock(return_value=submission_ok))
    assert job.hidden is exp_hidden


@pytest.mark.parametrize(
    argnames='submission_ok, jobs, exp_final_job',
    argvalues=(
        (True, (), None),
        (False, (Mock(is_finished=True), Mock(is_finished=False), Mock(is_finished=True)), None),
        (False, (Mock(is_finished=True, id='a'), Mock(is_finished=True, id='b'), Mock(is_finished=True, id='c')), 'c'),
    ),
)
def test_final_job_before_upload_property(submission_ok, jobs, exp_final_job, job, mocker):
    mocker.patch.object(type(job._tracker_jobs), 'submission_ok', PropertyMock(return_value=submission_ok))
    mocker.patch.object(type(job), 'jobs_before_upload', PropertyMock(return_value=jobs))
    if not exp_final_job:
        assert job.final_job_before_upload is None
    else:
        assert job.final_job_before_upload.id == exp_final_job
