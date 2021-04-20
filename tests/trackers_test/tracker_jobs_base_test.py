from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies.trackers.base import TrackerJobsBase


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


@pytest.fixture
def tracker():
    tracker = Mock()
    tracker.configure_mock(
        name='AsdF',
        config={
            'announce' : 'http://foo.bar',
            'source'   : 'AsdF',
            'exclude'  : ('a', 'b'),
        },
    )
    return tracker


def make_TestTrackerJobs(**kwargs):
    class TestTrackerJobs(TrackerJobsBase):
        jobs_before_upload = PropertyMock()

    default_kwargs = {
        'content_path': '',
        'tracker': Mock(),
        'image_host': '',
        'bittorrent_client': Mock(),
        'torrent_destination': '',
        'common_job_args': {},
    }
    return TestTrackerJobs(**{**default_kwargs, **kwargs})


def test_arguments():
    kwargs = {
        'content_path': Mock(),
        'tracker': Mock(),
        'image_host': Mock(),
        'bittorrent_client': Mock(),
        'torrent_destination': Mock(),
        'common_job_args': Mock(),
    }
    tracker_jobs = make_TestTrackerJobs(**kwargs)
    for k, v in kwargs.items():
        assert getattr(tracker_jobs, k) is v


def test_signals(mocker):
    Signal_mock = mocker.patch('upsies.utils.signal.Signal')
    tracker_jobs = make_TestTrackerJobs()
    assert tracker_jobs.signal is Signal_mock.return_value
    assert Signal_mock.call_args_list == [call('warning', 'error', 'exception')]
    tracker_jobs.warn('foo')
    assert Signal_mock.return_value.emit.call_args_list == [
        call('warning', 'foo'),
    ]
    tracker_jobs.error('bar')
    assert Signal_mock.return_value.emit.call_args_list == [
        call('warning', 'foo'),
        call('error', 'bar'),
    ]
    tracker_jobs.exception('baz')
    assert Signal_mock.return_value.emit.call_args_list == [
        call('warning', 'foo'),
        call('error', 'bar'),
        call('exception', 'baz'),
    ]


def test_jobs_after_upload(mocker):
    add_torrent_job_mock = mocker.patch('upsies.trackers.base.TrackerJobsBase.add_torrent_job')
    copy_torrent_job_mock = mocker.patch('upsies.trackers.base.TrackerJobsBase.copy_torrent_job')
    tracker_jobs = make_TestTrackerJobs()
    assert tracker_jobs.jobs_after_upload == (
        add_torrent_job_mock,
        copy_torrent_job_mock,
    )


@pytest.mark.parametrize(
    argnames='jobs_before_upload, exp_submission_ok',
    argvalues=(
        ((Mock(exit_code=0, is_enabled=True), Mock(exit_code=0, is_enabled=True), Mock(exit_code=0, is_enabled=True)), True),
        ((Mock(exit_code=0, is_enabled=True), Mock(exit_code=0, is_enabled=True), Mock(exit_code=1, is_enabled=True)), False),
        ((Mock(exit_code=0, is_enabled=True), Mock(exit_code=1, is_enabled=True), Mock(exit_code=0, is_enabled=True)), False),
        ((Mock(exit_code=1, is_enabled=True), Mock(exit_code=0, is_enabled=True), Mock(exit_code=0, is_enabled=True)), False),
        ((Mock(exit_code=1, is_enabled=False), Mock(exit_code=0, is_enabled=True), Mock(exit_code=0, is_enabled=True)), True),
        ((Mock(exit_code=0, is_enabled=False), Mock(exit_code=1, is_enabled=False), Mock(exit_code=0, is_enabled=True)), True),
        ((Mock(exit_code=0, is_enabled=False), Mock(exit_code=0, is_enabled=False), Mock(exit_code=1, is_enabled=False)), False),
        ((Mock(exit_code=0, is_enabled=False), Mock(exit_code=0, is_enabled=False), Mock(exit_code=0, is_enabled=False)), False),
    ),
)
def test_submission_ok(jobs_before_upload, exp_submission_ok, mocker):
    tracker_jobs = make_TestTrackerJobs()
    mocker.patch.object(type(tracker_jobs), 'jobs_before_upload', PropertyMock(return_value=jobs_before_upload))
    assert tracker_jobs.submission_ok == exp_submission_ok


def test_create_torrent_job(mocker):
    CreateTorrentJob_mock = mocker.patch('upsies.jobs.torrent.CreateTorrentJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker='mock tracker',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.create_torrent_job is CreateTorrentJob_mock.return_value
    assert CreateTorrentJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            tracker='mock tracker',
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]

def test_create_torrent_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.torrent.CreateTorrentJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker='mock tracker',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.create_torrent_job is tracker_jobs.create_torrent_job


def test_add_torrent_job_without_bittorrent_client_argument(mocker):
    AddTorrentJob_mock = mocker.patch('upsies.jobs.torrent.AddTorrentJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        bittorrent_client=None,
    )
    assert tracker_jobs.add_torrent_job is None
    assert AddTorrentJob_mock.call_args_list == []

def test_add_torrent_job_with_add_to_client_argument(mocker):
    AddTorrentJob_mock = mocker.patch('upsies.jobs.torrent.AddTorrentJob')
    mocker.patch('upsies.jobs.torrent.CreateTorrentJob')
    mocker.patch('upsies.utils.fs.dirname', Mock(return_value='path/to/content/dir'))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker='mock tracker',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        bittorrent_client='bittorrent client mock',
    )
    assert tracker_jobs.add_torrent_job is AddTorrentJob_mock.return_value
    assert AddTorrentJob_mock.call_args_list == [
        call(
            autostart=False,
            client='bittorrent client mock',
            download_path='path/to/content/dir',
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert tracker_jobs.create_torrent_job.signal.register.call_args_list == [
        call('output', tracker_jobs.add_torrent_job.enqueue),
        call('finished', tracker_jobs.finalize_add_torrent_job),
    ]

def test_add_torrent_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.torrent.AddTorrentJob', side_effect=(Mock(), Mock()))
    mocker.patch('upsies.jobs.torrent.CreateTorrentJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker='mock tracker',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        bittorrent_client='bittorrent client mock',
    )
    assert tracker_jobs.add_torrent_job is tracker_jobs.add_torrent_job


def test_finalize_add_torrent_job(mocker):
    mocker.patch('upsies.jobs.torrent.AddTorrentJob')
    mocker.patch('upsies.jobs.torrent.CreateTorrentJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker='mock tracker',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        bittorrent_client='bittorrent client mock',
    )
    mocker.patch.object(tracker_jobs, 'add_torrent_job')
    tracker_jobs.finalize_add_torrent_job('mock job')
    assert tracker_jobs.add_torrent_job.finalize.call_args_list == [call()]


def test_copy_torrent_job_without_torrent_destination_argument(mocker):
    CopyTorrentJob_mock = mocker.patch('upsies.jobs.torrent.CopyTorrentJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        torrent_destination=None,
    )
    assert tracker_jobs.copy_torrent_job is None
    assert CopyTorrentJob_mock.call_args_list == []

def test_copy_torrent_job_with_torrent_destination_argument(mocker):
    CopyTorrentJob_mock = mocker.patch('upsies.jobs.torrent.CopyTorrentJob')
    mocker.patch('upsies.jobs.torrent.CreateTorrentJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        torrent_destination='path/to/torrent/destination',
    )
    assert tracker_jobs.copy_torrent_job is CopyTorrentJob_mock.return_value
    assert CopyTorrentJob_mock.call_args_list == [
        call(
            autostart=False,
            destination='path/to/torrent/destination',
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert tracker_jobs.create_torrent_job.signal.register.call_args_list == [
        call('output', tracker_jobs.copy_torrent_job.enqueue),
        call('finished', tracker_jobs.finalize_copy_torrent_job),
    ]

def test_copy_torrent_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.torrent.CopyTorrentJob', side_effect=(Mock(), Mock()))
    mocker.patch('upsies.jobs.torrent.CreateTorrentJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        torrent_destination='path/to/torrent/destination',
    )
    assert tracker_jobs.copy_torrent_job is tracker_jobs.copy_torrent_job


def test_finalize_copy_torrent_job(mocker):
    mocker.patch('upsies.jobs.torrent.CopyTorrentJob')
    mocker.patch('upsies.jobs.torrent.CreateTorrentJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker='mock tracker',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        bittorrent_client='bittorrent client mock',
    )
    mocker.patch.object(tracker_jobs, 'copy_torrent_job')
    tracker_jobs.finalize_copy_torrent_job('mock job')
    assert tracker_jobs.copy_torrent_job.finalize.call_args_list == [call()]


def test_release_name_job(mocker):
    ReleaseNameJob_mock = mocker.patch('upsies.jobs.release_name.ReleaseNameJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.release_name_job is ReleaseNameJob_mock.return_value
    assert ReleaseNameJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]

def test_release_name_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.release_name.ReleaseNameJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.release_name_job is tracker_jobs.release_name_job


def test_imdb_job(mocker):
    SearchWebDbJob_mock = mocker.patch('upsies.jobs.webdb.SearchWebDbJob')
    mocker.patch('upsies.jobs.release_name.ReleaseNameJob')
    webdb_mock = mocker.patch('upsies.utils.webdbs.webdb')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.imdb_job is SearchWebDbJob_mock.return_value
    assert SearchWebDbJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            db=webdb_mock.return_value,
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert webdb_mock.call_args_list == [call('imdb')]
    assert tracker_jobs.imdb_job.signal.register.call_args_list == [
        call('output', tracker_jobs.release_name_job.fetch_info),
    ]

def test_imdb_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.webdb.SearchWebDbJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.imdb_job is tracker_jobs.imdb_job


def test_tmdb_job(mocker):
    SearchWebDbJob_mock = mocker.patch('upsies.jobs.webdb.SearchWebDbJob')
    webdb_mock = mocker.patch('upsies.utils.webdbs.webdb')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.tmdb_job is SearchWebDbJob_mock.return_value
    assert SearchWebDbJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            db=webdb_mock.return_value,
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert webdb_mock.call_args_list == [call('tmdb')]

def test_tmdb_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.webdb.SearchWebDbJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.tmdb_job is tracker_jobs.tmdb_job


def test_tvmaze_job(mocker):
    SearchWebDbJob_mock = mocker.patch('upsies.jobs.webdb.SearchWebDbJob')
    webdb_mock = mocker.patch('upsies.utils.webdbs.webdb')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.tvmaze_job is SearchWebDbJob_mock.return_value
    assert SearchWebDbJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            db=webdb_mock.return_value,
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert webdb_mock.call_args_list == [call('tvmaze')]

def test_tvmaze_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.webdb.SearchWebDbJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.tvmaze_job is tracker_jobs.tvmaze_job


@pytest.mark.parametrize(
    argnames='cli_args, exp_screenshots',
    argvalues=(
        (None, TrackerJobsBase.screenshots),
        (Mock(screenshots=123), 123),
    ),
    ids=lambda v: str(v),
)
def test_screenshots_job(cli_args, exp_screenshots, mocker):
    ScreenshotsJob_mock = mocker.patch('upsies.jobs.screenshots.ScreenshotsJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        cli_args=cli_args,
    )
    assert tracker_jobs.screenshots_job is ScreenshotsJob_mock.return_value
    assert ScreenshotsJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            count=exp_screenshots,
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]

def test_screenshots_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.screenshots.ScreenshotsJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.screenshots_job is tracker_jobs.screenshots_job


def test_upload_screenshots_job_without_image_host_argument(mocker):
    ImageHostJob_mock = mocker.patch('upsies.jobs.imghost.ImageHostJob')
    mocker.patch('upsies.jobs.screenshots.ScreenshotsJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        image_host=None,
    )
    assert tracker_jobs.upload_screenshots_job is None
    assert ImageHostJob_mock.call_args_list == []

def test_upload_screenshots_job_with_image_host_argument(mocker):
    ImageHostJob_mock = mocker.patch('upsies.jobs.imghost.ImageHostJob')
    mocker.patch('upsies.jobs.screenshots.ScreenshotsJob')
    image_host_mock = Mock()
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        image_host=image_host_mock,
    )
    assert tracker_jobs.upload_screenshots_job is ImageHostJob_mock.return_value
    assert ImageHostJob_mock.call_args_list == [
        call(
            imghost=image_host_mock,
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    # ScreenshotsJob also registers a callback for "timestamps", but that
    # doesn't concern us
    assert tracker_jobs.screenshots_job.signal.register.call_args_list[-2:] == [
        call('output', tracker_jobs.upload_screenshots_job.enqueue),
        call('finished', tracker_jobs.finalize_upload_screenshots_job),
    ]

def test_upload_screenshots_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.imghost.ImageHostJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        image_host=Mock(),
    )
    assert tracker_jobs.upload_screenshots_job is tracker_jobs.upload_screenshots_job


def test_finalize_upload_screenshots_job(mocker):
    mocker.patch('upsies.jobs.screenshots.ScreenshotsJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker='mock tracker',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        bittorrent_client='bittorrent client mock',
    )
    mocker.patch.object(tracker_jobs, 'upload_screenshots_job')
    tracker_jobs.finalize_upload_screenshots_job('mock job')
    assert tracker_jobs.upload_screenshots_job.finalize.call_args_list == [call()]


def test_mediainfo_job(mocker):
    MediainfoJob_mock = mocker.patch('upsies.jobs.mediainfo.MediainfoJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.mediainfo_job is MediainfoJob_mock.return_value
    assert MediainfoJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]

def test_mediainfo_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.mediainfo.MediainfoJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.mediainfo_job is tracker_jobs.mediainfo_job


def test_scene_check_job(mocker):
    SceneCheckJob_mock = mocker.patch('upsies.jobs.scene.SceneCheckJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.scene_check_job is SceneCheckJob_mock.return_value
    assert SceneCheckJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]

def test_scene_check_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.scene.SceneCheckJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.scene_check_job is tracker_jobs.scene_check_job
