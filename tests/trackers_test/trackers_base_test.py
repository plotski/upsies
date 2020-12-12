from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies.trackers.base import TrackerBase
from upsies import trackers


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_trackers(mocker):
    existing_trackers = (Mock(), Mock(), Mock())
    submodules_mock = mocker.patch('upsies.utils.submodules')
    subclasses_mock = mocker.patch('upsies.utils.subclasses', return_value=existing_trackers)
    assert trackers.trackers() == existing_trackers
    assert submodules_mock.call_args_list == [call('upsies.trackers')]
    assert subclasses_mock.call_args_list == [call(trackers.base.TrackerBase, submodules_mock.return_value)]


def test_tracker_returns_TrackerBase_instance(mocker):
    existing_trackers = (Mock(), Mock(), Mock())
    existing_trackers[0].configure_mock(name='foo')
    existing_trackers[1].configure_mock(name='bar')
    existing_trackers[2].configure_mock(name='baz')
    mocker.patch('upsies.trackers.trackers', return_value=existing_trackers)
    assert trackers.tracker('bar', x=123) is existing_trackers[1].return_value
    assert existing_trackers[1].call_args_list == [call(x=123)]

def test_tracker_fails_to_find_class(mocker):
    existing_trackers = (Mock(), Mock(), Mock())
    existing_trackers[0].configure_mock(name='foo')
    existing_trackers[1].configure_mock(name='bar')
    existing_trackers[2].configure_mock(name='baz')
    mocker.patch('upsies.trackers.trackers', return_value=existing_trackers)
    with pytest.raises(ValueError, match='^Unsupported tracker: bam$'):
        trackers.tracker('bam', x=123)
    for t in existing_trackers:
        assert t.call_args_list == []


def make_TestTracker(**kwargs):
    class TestTracker(TrackerBase):
        name = 'asdf'
        label = 'AsdF'
        jobs_before_upload = PropertyMock()
        login = AsyncMock()
        logout = AsyncMock()
        upload = AsyncMock()

    return TestTracker(**kwargs)


@pytest.mark.parametrize('method', TrackerBase.__abstractmethods__)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in TrackerBase.__abstractmethods__}
    del attrs[method]
    cls = type('Tracker', (TrackerBase,), attrs)
    # Python 3.9 changed "methods" to "method"
    exp_msg = rf"^Can't instantiate abstract class Tracker with abstract methods? {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def test_config():
    tracker = make_TestTracker(
        config={'username': 'foo', 'password': 'bar'},
    )
    assert tracker.config == {'username': 'foo', 'password': 'bar'}


def test_info():
    tracker = make_TestTracker(
        config={},
        this='that',
        something=(1, 2, 3),
    )
    assert tracker.info.this == 'that'
    assert tracker.info.something == (1, 2, 3)


def test_jobs_after_upload(mocker):
    add_torrent_job_mock = mocker.patch('upsies.trackers.TrackerBase.add_torrent_job', Mock())
    copy_torrent_job_mock = mocker.patch('upsies.trackers.TrackerBase.copy_torrent_job', Mock())
    tracker = make_TestTracker(config={})
    assert tracker.jobs_after_upload == (
        add_torrent_job_mock,
        copy_torrent_job_mock,
    )


def test_create_torrent_job(mocker):
    CreateTorrentJob_mock = mocker.patch('upsies.jobs.torrent.CreateTorrentJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path=Mock(),
    )
    assert tracker.create_torrent_job is CreateTorrentJob_mock.return_value
    assert CreateTorrentJob_mock.call_args_list == [
        call(
            homedir=tracker.info.homedir,
            ignore_cache=tracker.info.ignore_cache,
            content_path=tracker.info.content_path,
            tracker_name=tracker.name,
            tracker_config=tracker.config,
        ),
    ]


def test_add_torrent_job_without_add_to_client_argument(mocker):
    AddTorrentJob_mock = mocker.patch('upsies.jobs.torrent.AddTorrentJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path=Mock(),
        add_to_client=None,
    )
    assert tracker.add_torrent_job is None
    assert AddTorrentJob_mock.call_args_list == []

def test_add_torrent_job_with_add_to_client_argument(mocker):
    AddTorrentJob_mock = mocker.patch('upsies.jobs.torrent.AddTorrentJob', Mock())
    mocker.patch('upsies.jobs.torrent.CreateTorrentJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path='path/to/content/foo',
        add_to_client=Mock(),
    )
    assert tracker.add_torrent_job is AddTorrentJob_mock.return_value
    assert AddTorrentJob_mock.call_args_list == [
        call(
            homedir=tracker.info.homedir,
            ignore_cache=tracker.info.ignore_cache,
            client=tracker.info.add_to_client,
            download_path='path/to/content',
        ),
    ]
    assert (call('output', tracker.add_torrent_job.add)
            in tracker.create_torrent_job.signal.register.call_args_list)
    assert (call('finished', tracker.add_torrent_job.finalize)
            in tracker.create_torrent_job.signal.register.call_args_list)


def test_copy_torrent_job_without_torrent_destination_argument(mocker):
    CopyTorrentJob_mock = mocker.patch('upsies.jobs.torrent.CopyTorrentJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path=Mock(),
        torrent_destination=None,
    )
    assert tracker.copy_torrent_job is None
    assert CopyTorrentJob_mock.call_args_list == []

def test_copy_torrent_job_with_torrent_destination_argument(mocker):
    CopyTorrentJob_mock = mocker.patch('upsies.jobs.torrent.CopyTorrentJob', Mock())
    mocker.patch('upsies.jobs.torrent.CreateTorrentJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path='path/to/content/foo',
        torrent_destination=Mock(),
    )
    assert tracker.copy_torrent_job is CopyTorrentJob_mock.return_value
    assert CopyTorrentJob_mock.call_args_list == [
        call(
            homedir=tracker.info.homedir,
            ignore_cache=tracker.info.ignore_cache,
            destination=tracker.info.torrent_destination,
        ),
    ]
    assert (call('output', tracker.copy_torrent_job.copy)
            in tracker.create_torrent_job.signal.register.call_args_list)
    assert (call('finished', tracker.copy_torrent_job.finish)
            in tracker.create_torrent_job.signal.register.call_args_list)


def test_release_name_job(mocker):
    ReleaseNameJob_mock = mocker.patch('upsies.jobs.release_name.ReleaseNameJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path=Mock(),
    )
    assert tracker.release_name_job is ReleaseNameJob_mock.return_value
    assert ReleaseNameJob_mock.call_args_list == [
        call(
            homedir=tracker.info.homedir,
            ignore_cache=tracker.info.ignore_cache,
            content_path=tracker.info.content_path,
        ),
    ]


def test_imdb_job(mocker):
    SearchDbJob_mock = mocker.patch('upsies.jobs.search.SearchDbJob', Mock())
    mocker.patch('upsies.jobs.release_name.ReleaseNameJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path=Mock(),
    )
    assert tracker.imdb_job is SearchDbJob_mock.return_value
    assert SearchDbJob_mock.call_args_list == [
        call(
            homedir=tracker.info.homedir,
            ignore_cache=tracker.info.ignore_cache,
            content_path=tracker.info.content_path,
            db='imdb',
        ),
    ]
    assert tracker.imdb_job.signal.register.call_args_list == [
        call('output', tracker.release_name_job.fetch_info),
    ]


def test_tmdb_job(mocker):
    SearchDbJob_mock = mocker.patch('upsies.jobs.search.SearchDbJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path=Mock(),
    )
    assert tracker.tmdb_job is SearchDbJob_mock.return_value
    assert SearchDbJob_mock.call_args_list == [
        call(
            homedir=tracker.info.homedir,
            ignore_cache=tracker.info.ignore_cache,
            content_path=tracker.info.content_path,
            db='tmdb',
        ),
    ]


def test_tvmaze_job(mocker):
    SearchDbJob_mock = mocker.patch('upsies.jobs.search.SearchDbJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path=Mock(),
    )
    assert tracker.tvmaze_job is SearchDbJob_mock.return_value
    assert SearchDbJob_mock.call_args_list == [
        call(
            homedir=tracker.info.homedir,
            ignore_cache=tracker.info.ignore_cache,
            content_path=tracker.info.content_path,
            db='tvmaze',
        ),
    ]


def test_screenshots_job(mocker):
    ScreenshotsJob_mock = mocker.patch('upsies.jobs.screenshots.ScreenshotsJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path=Mock(),
    )
    assert tracker.screenshots_job is ScreenshotsJob_mock.return_value
    assert ScreenshotsJob_mock.call_args_list == [
        call(
            homedir=tracker.info.homedir,
            ignore_cache=tracker.info.ignore_cache,
            content_path=tracker.info.content_path,
        ),
    ]


def test_upload_screenshots_job_without_image_host_argument(mocker):
    ImageHostJob_mock = mocker.patch('upsies.jobs.imghost.ImageHostJob', Mock())
    mocker.patch('upsies.jobs.screenshots.ScreenshotsJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path=Mock(),
        image_host=None,
    )
    assert tracker.upload_screenshots_job is None
    assert ImageHostJob_mock.call_args_list == []

def test_upload_screenshots_job_with_image_host_argument(mocker):
    ImageHostJob_mock = mocker.patch('upsies.jobs.imghost.ImageHostJob', Mock())
    mocker.patch('upsies.jobs.screenshots.ScreenshotsJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path=Mock(),
        image_host=Mock(),
    )
    assert tracker.upload_screenshots_job is ImageHostJob_mock.return_value
    assert ImageHostJob_mock.call_args_list == [
        call(
            homedir=tracker.info.homedir,
            ignore_cache=tracker.info.ignore_cache,
            imghost=tracker.info.image_host,
        ),
    ]
    assert (call('output', tracker.upload_screenshots_job.upload)
            in tracker.screenshots_job.signal.register.call_args_list)
    assert (call('finished', tracker.upload_screenshots_job.finalize)
            in tracker.screenshots_job.signal.register.call_args_list)


def test_mediainfo_job(mocker):
    MediainfoJob_mock = mocker.patch('upsies.jobs.mediainfo.MediainfoJob', Mock())
    tracker = make_TestTracker(
        config=Mock(),
        homedir=Mock(),
        ignore_cache=Mock(),
        content_path=Mock(),
    )
    assert tracker.mediainfo_job is MediainfoJob_mock.return_value
    assert MediainfoJob_mock.call_args_list == [
        call(
            homedir=tracker.info.homedir,
            ignore_cache=tracker.info.ignore_cache,
            content_path=tracker.info.content_path,
        ),
    ]
