from unittest.mock import Mock, PropertyMock, call

from upsies.trackers.base import TrackerJobsBase


def make_TestTrackerJobs(**kwargs):
    class TestTrackerJobs(TrackerJobsBase):
        jobs_before_upload = PropertyMock()

    default_kwargs = {
        'tracker_name': '',
        'tracker_config': {},
        'content_path': '',
        'image_host': '',
        'bittorrent_client': Mock(),
        'torrent_destination': '',
        'common_job_args': {},
    }
    return TestTrackerJobs(**{**default_kwargs, **kwargs})


def test_arguments():
    kwargs = {
        'tracker_name': Mock(),
        'tracker_config': Mock(),
        'content_path': Mock(),
        'image_host': Mock(),
        'bittorrent_client': Mock(),
        'torrent_destination': Mock(),
        'common_job_args': Mock(),
    }
    tracker_jobs = make_TestTrackerJobs(**kwargs)
    for k, v in kwargs.items():
        assert getattr(tracker_jobs, k) is v


def test_jobs_after_upload(mocker):
    add_torrent_job_mock = mocker.patch('upsies.trackers.base.TrackerJobsBase.add_torrent_job', Mock())
    copy_torrent_job_mock = mocker.patch('upsies.trackers.base.TrackerJobsBase.copy_torrent_job', Mock())
    tracker_jobs = make_TestTrackerJobs()
    assert tracker_jobs.jobs_after_upload == (
        add_torrent_job_mock,
        copy_torrent_job_mock,
    )


def test_create_torrent_job(mocker):
    CreateTorrentJob_mock = mocker.patch('upsies.jobs.torrent.CreateTorrentJob', Mock())
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker_name='asdf',
        tracker_config={'announce': 'http://foo:1234/announce', 'source': 'AsdF'},
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    # Return value must be singleton
    assert tracker_jobs.create_torrent_job is CreateTorrentJob_mock.return_value
    assert tracker_jobs.create_torrent_job is CreateTorrentJob_mock.return_value
    assert CreateTorrentJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            tracker_name='asdf',
            tracker_config={'announce': 'http://foo:1234/announce', 'source': 'AsdF'},
            homedir='path/to/home',
            ignore_cache='mock bool',
        ),
    ]


def test_add_torrent_job_without_bittorrent_client_argument(mocker):
    AddTorrentJob_mock = mocker.patch('upsies.jobs.torrent.AddTorrentJob', Mock())
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        tracker_name='asdf',
        tracker_config={'announce': 'http://foo:1234/announce', 'source': 'AsdF'},
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
        bittorrent_client=None,
    )
    # Return value must be singleton
    assert tracker_jobs.add_torrent_job is None
    assert tracker_jobs.add_torrent_job is None
    assert AddTorrentJob_mock.call_args_list == []

def test_add_torrent_job_with_add_to_client_argument(mocker):
    AddTorrentJob_mock = mocker.patch('upsies.jobs.torrent.AddTorrentJob', Mock())
    mocker.patch('upsies.jobs.torrent.CreateTorrentJob', Mock())
    mocker.patch('upsies.utils.fs.dirname', Mock(return_value='path/to/content/dir'))
    bittorrent_client_mock = Mock()
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
        bittorrent_client=bittorrent_client_mock,
    )
    # Return value must be singleton
    assert tracker_jobs.add_torrent_job is AddTorrentJob_mock.return_value
    assert tracker_jobs.add_torrent_job is AddTorrentJob_mock.return_value
    assert AddTorrentJob_mock.call_args_list == [
        call(
            client=bittorrent_client_mock,
            download_path='path/to/content/dir',
            autostart=False,
            homedir='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert tracker_jobs.create_torrent_job.signal.register.call_args_list == [
        call('output', tracker_jobs.add_torrent_job.enqueue),
        call('finished', tracker_jobs.add_torrent_job.finalize),
    ]


def test_copy_torrent_job_without_torrent_destination_argument(mocker):
    CopyTorrentJob_mock = mocker.patch('upsies.jobs.torrent.CopyTorrentJob', Mock())
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
        torrent_destination=None,
    )
    assert tracker_jobs.copy_torrent_job is None
    assert CopyTorrentJob_mock.call_args_list == []

def test_copy_torrent_job_with_torrent_destination_argument(mocker):
    CopyTorrentJob_mock = mocker.patch('upsies.jobs.torrent.CopyTorrentJob', Mock())
    mocker.patch('upsies.jobs.torrent.CreateTorrentJob', Mock())
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
        torrent_destination='path/to/torrent/destination',
    )
    # Return value must be singleton
    assert tracker_jobs.copy_torrent_job is CopyTorrentJob_mock.return_value
    assert tracker_jobs.copy_torrent_job is CopyTorrentJob_mock.return_value
    assert CopyTorrentJob_mock.call_args_list == [
        call(
            destination='path/to/torrent/destination',
            autostart=False,
            homedir='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert tracker_jobs.create_torrent_job.signal.register.call_args_list == [
        call('output', tracker_jobs.copy_torrent_job.enqueue),
        call('finished', tracker_jobs.copy_torrent_job.finalize),
    ]


def test_release_name_job(mocker):
    ReleaseNameJob_mock = mocker.patch('upsies.jobs.release_name.ReleaseNameJob', Mock())
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    # Return value must be singleton
    assert tracker_jobs.release_name_job is ReleaseNameJob_mock.return_value
    assert tracker_jobs.release_name_job is ReleaseNameJob_mock.return_value
    assert ReleaseNameJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            homedir='path/to/home',
            ignore_cache='mock bool',
        ),
    ]


def test_imdb_job(mocker):
    SearchWebDbJob_mock = mocker.patch('upsies.jobs.webdb.SearchWebDbJob', Mock())
    mocker.patch('upsies.jobs.release_name.ReleaseNameJob', Mock())
    webdb_mock = mocker.patch('upsies.utils.webdbs.webdb')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    # Return value must be singleton
    assert tracker_jobs.imdb_job is SearchWebDbJob_mock.return_value
    assert tracker_jobs.imdb_job is SearchWebDbJob_mock.return_value
    assert SearchWebDbJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            db=webdb_mock.return_value,
            homedir='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert webdb_mock.call_args_list == [call('imdb')]
    assert tracker_jobs.imdb_job.signal.register.call_args_list == [
        call('output', tracker_jobs.release_name_job.fetch_info),
    ]


def test_tmdb_job(mocker):
    SearchWebDbJob_mock = mocker.patch('upsies.jobs.webdb.SearchWebDbJob', Mock())
    webdb_mock = mocker.patch('upsies.utils.webdbs.webdb')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    # Return value must be singleton
    assert tracker_jobs.tmdb_job is SearchWebDbJob_mock.return_value
    assert tracker_jobs.tmdb_job is SearchWebDbJob_mock.return_value
    assert SearchWebDbJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            db=webdb_mock.return_value,
            homedir='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert webdb_mock.call_args_list == [call('tmdb')]


def test_tvmaze_job(mocker):
    SearchWebDbJob_mock = mocker.patch('upsies.jobs.webdb.SearchWebDbJob', Mock())
    webdb_mock = mocker.patch('upsies.utils.webdbs.webdb')
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    # Return value must be singleton
    assert tracker_jobs.tvmaze_job is SearchWebDbJob_mock.return_value
    assert tracker_jobs.tvmaze_job is SearchWebDbJob_mock.return_value
    assert SearchWebDbJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            db=webdb_mock.return_value,
            homedir='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    assert webdb_mock.call_args_list == [call('tvmaze')]


def test_screenshots_job(mocker):
    ScreenshotsJob_mock = mocker.patch('upsies.jobs.screenshots.ScreenshotsJob', Mock())
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    # Return value must be singleton
    assert tracker_jobs.screenshots_job is ScreenshotsJob_mock.return_value
    assert tracker_jobs.screenshots_job is ScreenshotsJob_mock.return_value
    assert ScreenshotsJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            homedir='path/to/home',
            ignore_cache='mock bool',
        ),
    ]


def test_upload_screenshots_job_without_image_host_argument(mocker):
    ImageHostJob_mock = mocker.patch('upsies.jobs.imghost.ImageHostJob', Mock())
    mocker.patch('upsies.jobs.screenshots.ScreenshotsJob', Mock())
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
        image_host=None,
    )
    # Return value must be singleton
    assert tracker_jobs.upload_screenshots_job is None
    assert tracker_jobs.upload_screenshots_job is None
    assert ImageHostJob_mock.call_args_list == []

def test_upload_screenshots_job_with_image_host_argument(mocker):
    ImageHostJob_mock = mocker.patch('upsies.jobs.imghost.ImageHostJob', Mock())
    mocker.patch('upsies.jobs.screenshots.ScreenshotsJob', Mock())
    image_host_mock = Mock()
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
        image_host=image_host_mock,
    )
    # Return value must be singleton
    assert tracker_jobs.upload_screenshots_job is ImageHostJob_mock.return_value
    assert tracker_jobs.upload_screenshots_job is ImageHostJob_mock.return_value
    assert ImageHostJob_mock.call_args_list == [
        call(
            imghost=image_host_mock,
            homedir='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
    # ScreenshotsJob also registers a callback for "timestamps", but that
    # doesn't concern us
    assert tracker_jobs.screenshots_job.signal.register.call_args_list[-2:] == [
        call('output', tracker_jobs.upload_screenshots_job.enqueue),
        call('finished', tracker_jobs.upload_screenshots_job.finalize),
    ]


def test_mediainfo_job(mocker):
    MediainfoJob_mock = mocker.patch('upsies.jobs.mediainfo.MediainfoJob', Mock())
    tracker_jobs = make_TestTrackerJobs(
        content_path='path/to/content',
        common_job_args={'homedir': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    # Return value must be singleton
    assert tracker_jobs.mediainfo_job is MediainfoJob_mock.return_value
    assert tracker_jobs.mediainfo_job is MediainfoJob_mock.return_value
    assert MediainfoJob_mock.call_args_list == [
        call(
            content_path='path/to/content',
            homedir='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
