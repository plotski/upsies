import builtins
import random
import re
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies import utils
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
        options={
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
        'exclude_files': (),
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
        'exclude_files': Mock(),
        'common_job_args': Mock(),
        'options': {'mock': 'config'},
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


def test_imdb():
    tracker_jobs = make_TestTrackerJobs()
    assert isinstance(tracker_jobs.imdb, utils.webdbs.imdb.ImdbApi)

def test_tmdb():
    tracker_jobs = make_TestTrackerJobs()
    assert isinstance(tracker_jobs.tvmaze, utils.webdbs.tvmaze.TvmazeApi)

def test_tvmaze():
    tracker_jobs = make_TestTrackerJobs()
    assert isinstance(tracker_jobs.tvmaze, utils.webdbs.tvmaze.TvmazeApi)


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
    # Randomly insert disabled job
    jobs_before_upload = list(jobs_before_upload)
    jobs_before_upload.insert(random.randint(0, len(jobs_before_upload)), None)
    tracker_jobs = make_TestTrackerJobs()
    mocker.patch.object(type(tracker_jobs), 'jobs_before_upload', PropertyMock(return_value=jobs_before_upload))
    assert tracker_jobs.submission_ok == exp_submission_ok


def test_get_job_name(tracker):
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker=tracker,
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.get_job_name('foo') == f'{tracker.name}-foo'
    assert tracker_jobs.get_job_name(f'{tracker.name}-foo') == f'{tracker.name}-foo'


def test_create_torrent_job(mocker):
    CreateTorrentJob_mock = mocker.patch('upsies.jobs.torrent.CreateTorrentJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker='mock tracker',
        exclude_files=('a', 'b', 'c'),
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.create_torrent_job is CreateTorrentJob_mock.return_value
    assert CreateTorrentJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            tracker='mock tracker',
            exclude_files=('a', 'b', 'c'),
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


def test_release_name(mocker):
    ReleaseName_mock = mocker.patch('upsies.utils.release.ReleaseName')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.release_name is ReleaseName_mock.return_value
    assert ReleaseName_mock.call_args_list == [
        call(
            path='path/to/content',
            translate=tracker_jobs.release_name_translation,
        ),
    ]


def test_release_name_job(tracker, mocker):
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker=tracker,
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    release_name_mock = Mock()
    mocker.patch.object(type(tracker_jobs), 'release_name', PropertyMock(return_value=release_name_mock))
    assert tracker_jobs.release_name_job is TextFieldJob_mock.return_value
    assert TextFieldJob_mock.call_args_list == [
        call(
            name=f'{tracker.name}-release-name',
            label='Release Name',
            text=str(release_name_mock),
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert tracker_jobs.release_name_job.signal.register.call_args_list == [
        call('output', release_name_mock.set_release_info)
    ]

def test_release_name_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.release_name.ReleaseNameJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.release_name_job is tracker_jobs.release_name_job


def test_update_release_name(mocker):
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )

    mocker.patch.object(type(tracker_jobs), 'release_name', PropertyMock())
    mocker.patch.object(type(tracker_jobs), 'release_name_job', PropertyMock())

    tracker_jobs._update_release_name('tt123456')
    assert tracker_jobs.release_name_job.add_task.call_args_list == [
        call(tracker_jobs.release_name_job.fetch_text.return_value),
    ]
    assert tracker_jobs.release_name_job.fetch_text.call_args_list == [
        call(
            coro=tracker_jobs.release_name.fetch_info.return_value,
            error_is_fatal=False,
        ),
    ]
    assert tracker_jobs.release_name.fetch_info.call_args_list == [call(imdb_id='tt123456')]


def test_imdb_job(mocker):
    WebDbSearchJob_mock = mocker.patch('upsies.jobs.webdb.WebDbSearchJob')
    mocker.patch('upsies.jobs.release_name.ReleaseNameJob')
    webdb_mock = mocker.patch('upsies.utils.webdbs.webdb')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.imdb_job is WebDbSearchJob_mock.return_value
    assert WebDbSearchJob_mock.call_args_list == [
        call(
            query='path/to/content',
            db=webdb_mock.return_value,
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert webdb_mock.call_args_list == [call('imdb')]
    assert tracker_jobs.imdb_job.signal.register.call_args_list == [
        call('output', tracker_jobs._update_release_name),
    ]

def test_imdb_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.webdb.WebDbSearchJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.imdb_job is tracker_jobs.imdb_job


def test_tmdb_job(mocker):
    WebDbSearchJob_mock = mocker.patch('upsies.jobs.webdb.WebDbSearchJob')
    webdb_mock = mocker.patch('upsies.utils.webdbs.webdb')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.tmdb_job is WebDbSearchJob_mock.return_value
    assert WebDbSearchJob_mock.call_args_list == [
        call(
            query='path/to/content',
            db=webdb_mock.return_value,
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert webdb_mock.call_args_list == [call('tmdb')]

def test_tmdb_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.webdb.WebDbSearchJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.tmdb_job is tracker_jobs.tmdb_job


def test_tvmaze_job(mocker):
    WebDbSearchJob_mock = mocker.patch('upsies.jobs.webdb.WebDbSearchJob')
    webdb_mock = mocker.patch('upsies.utils.webdbs.webdb')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.tvmaze_job is WebDbSearchJob_mock.return_value
    assert WebDbSearchJob_mock.call_args_list == [
        call(
            query='path/to/content',
            db=webdb_mock.return_value,
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert webdb_mock.call_args_list == [call('tvmaze')]

def test_tvmaze_job_is_singleton(mocker):
    mocker.patch('upsies.jobs.webdb.WebDbSearchJob', side_effect=(Mock(), Mock()))
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.tvmaze_job is tracker_jobs.tvmaze_job


def test_screenshots_job(mocker):
    ScreenshotsJob_mock = mocker.patch('upsies.jobs.screenshots.ScreenshotsJob')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
        options={'screenshots': 123},
    )
    assert tracker_jobs.screenshots_job is ScreenshotsJob_mock.return_value
    assert ScreenshotsJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            count=123,
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


def test_image_host_config():
    assert TrackerJobsBase.image_host_config == {}


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
    mocker.patch('upsies.jobs.screenshots.ScreenshotsJob')
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


@pytest.mark.parametrize('autofinish', (True, False), ids=lambda v: 'autofinish' if v else 'no autofinish')
@pytest.mark.parametrize(
    argnames='autodetected, exp_choices, exp_focused',
    argvalues=(
        ('', [('8k', 8000), ('9k', 9000), ('10k', 10000)], None),
        ('5', [('8k', 8000), ('9k', 9000), ('10k', 10000)], None),
        ('8', [('8k (autodetected)', 8000), ('9k', 9000), ('10k', 10000)], ('8k (autodetected)', 8000)),
        ('9', [('8k', 8000), ('9k (autodetected)', 9000), ('10k', 10000)], ('9k (autodetected)', 9000)),
        ('10', [('8k', 8000), ('9k', 9000), ('10k (autodetected)', 10000)], ('10k (autodetected)', 10000)),
    ),
)
@pytest.mark.asyncio
async def test_make_choice_job_with_regex_autofocus(autodetected, exp_choices, exp_focused, autofinish, tracker, mocker):
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker=tracker,
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    mocker.patch.object(type(tracker_jobs), 'common_job_args', PropertyMock(return_value={'foo': 'bar'}))
    ChoiceJob_mock = mocker.patch('upsies.jobs.dialog.ChoiceJob')
    ChoiceJob_mock.return_value.choice = None
    job = tracker_jobs.make_choice_job(
        name='foo',
        label='Foo',
        options=(
            {'label': '8k', 'value': 8000, 'regex': re.compile(r'8')},
            {'label': '9k', 'value': 9000, 'regex': re.compile(r'9')},
            {'label': '10k', 'value': 10000, 'regex': re.compile(r'10')},
        ),
        autodetected=autodetected,
        autofinish=autofinish,
        condition='mock condition',
        callbacks='mock callbacks',
    )
    assert ChoiceJob_mock.call_args_list == [call(
        name=f'{tracker.name}-foo',
        label='Foo',
        condition='mock condition',
        callbacks='mock callbacks',
        choices=exp_choices,
        focused=exp_focused,
        foo='bar',
    )]
    if autofinish and exp_focused:
        assert job.choice == exp_focused
    else:
        assert job.choice is None

@pytest.mark.parametrize('autofinish', (True, False), ids=lambda v: 'autofinish' if v else 'no autofinish')
@pytest.mark.parametrize(
    argnames='autodetected, exp_choices, exp_focused',
    argvalues=(
        ('', [('8k', 8000), ('9k', 9000), ('10k', 10000)], None),
        ('5', [('8k', 8000), ('9k', 9000), ('10k', 10000)], None),
        ('8', [('8k (autodetected)', 8000), ('9k', 9000), ('10k', 10000)], ('8k (autodetected)', 8000)),
        ('9', [('8k', 8000), ('9k (autodetected)', 9000), ('10k', 10000)], ('9k (autodetected)', 9000)),
        ('10', [('8k', 8000), ('9k', 9000), ('10k (autodetected)', 10000)], ('10k (autodetected)', 10000)),
    ),
)
@pytest.mark.asyncio
async def test_make_choice_job_with_match_autofocus(autodetected, exp_choices, exp_focused, autofinish, tracker, mocker):
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker=tracker,
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    mocker.patch.object(type(tracker_jobs), 'common_job_args', PropertyMock(return_value={'foo': 'bar'}))
    ChoiceJob_mock = mocker.patch('upsies.jobs.dialog.ChoiceJob')
    ChoiceJob_mock.return_value.choice = None
    job = tracker_jobs.make_choice_job(
        name='foo',
        label='Foo',
        options=(
            {'label': '8k', 'value': 8000, 'match': lambda v: v.startswith('8')},
            {'label': '9k', 'value': 9000, 'match': lambda v: v.startswith('9')},
            {'label': '10k', 'value': 10000, 'match': lambda v: v.startswith('10')},
        ),
        autodetected=autodetected,
        autofinish=autofinish,
        condition='mock condition',
    )
    assert ChoiceJob_mock.call_args_list == [call(
        name=f'{tracker.name}-foo',
        label='Foo',
        condition='mock condition',
        callbacks={},
        choices=exp_choices,
        focused=exp_focused,
        foo='bar',
    )]
    if autofinish and exp_focused:
        assert job.choice == exp_focused
    else:
        assert job.choice is None


@pytest.mark.parametrize(
    argnames='job, slice, exp_error, exp_output',
    argvalues=(
        (Mock(is_finished=False, output=('foo', 'bar', 'baz')),
         None,
         'Unfinished job: asdf',
         ()),
        (Mock(is_finished=True, output=('foo', 'bar', 'baz')),
         None,
         None,
         ('foo', 'bar', 'baz')),
        (Mock(is_finished=True, output=('foo', 'bar', 'baz')),
         0,
         None,
         'foo'),
        (Mock(is_finished=True, output=('foo', 'bar', 'baz')),
         1,
         None,
         'bar'),
        (Mock(is_finished=True, output=('foo', 'bar', 'baz')),
         2,
         None,
         'baz'),
        (Mock(is_finished=True, output=('foo', 'bar', 'baz')),
         builtins.slice(1, 3),
         None,
         ('bar', 'baz')),
        (Mock(is_finished=True, output=('foo', 'bar', 'baz')),
         10,
         "Job finished with insufficient output: asdf: ('foo', 'bar', 'baz')",
         ()),
    ),
)
@pytest.mark.asyncio
async def test_get_job_output(job, slice, exp_error, exp_output, mocker):
    job.configure_mock(name='asdf')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    if exp_error:
        with pytest.raises(RuntimeError, match=rf'^{re.escape(exp_error)}$'):
            tracker_jobs.get_job_output(job, slice)
    else:
        output = tracker_jobs.get_job_output(job, slice)
        assert output == exp_output


@pytest.mark.parametrize(
    argnames='job, attribute, exp_error, exp_value',
    argvalues=(
        (Mock(is_finished=False, foo='bar'), 'foo', 'Unfinished job: asdf', ''),
        (Mock(is_finished=True, foo='bar'), 'foo', None, 'bar'),
    ),
)
@pytest.mark.asyncio
async def test_get_job_attribute(job, attribute, exp_error, exp_value, mocker):
    job.configure_mock(name='asdf')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    if exp_error:
        with pytest.raises(RuntimeError, match=rf'^{re.escape(exp_error)}$'):
            tracker_jobs.get_job_attribute(job, attribute)
    else:
        value = tracker_jobs.get_job_attribute(job, attribute)
        assert value == exp_value
