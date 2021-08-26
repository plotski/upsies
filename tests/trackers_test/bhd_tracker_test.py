import io
from unittest.mock import Mock, call

import pytest

from upsies import errors, utils
from upsies.trackers.bhd import BhdTracker, BhdTrackerConfig, BhdTrackerJobs
from upsies.utils.http import Result


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_name_attribute():
    assert BhdTracker.name == 'bhd'


def test_label_attribute():
    assert BhdTracker.label == 'BHD'


def test_TrackerConfig_attribute():
    assert BhdTracker.TrackerConfig is BhdTrackerConfig


def test_TrackerJobs_attribute():
    assert BhdTracker.TrackerJobs is BhdTrackerJobs


def test_argument_definitions():
    assert BhdTracker.argument_definitions == {
        ('--draft', '-d'): {
            'help': 'Upload as draft',
            'action': 'store_true',
            'default': None,
        },
        ('--personal-rip', '-p'): {
            'help': 'Tag as your own encode',
            'action': 'store_true',
        },
        ('--custom-edition', '-e'): {
            'help': 'Non-standard edition, e.g. "Final Cut"',
            'default': '',
        },
        ('--special', '-s'): {
            'help': 'Tag as special episode, e.g. Christmas special (ignored for movie uploads)',
            'action': 'store_true',
        },
        ('--description', '--desc'): {
            'help': 'Only generate description (do not upload anything)',
            'action': 'store_true',
        },
        ('--screenshots', '--ss'): {
            'help': ('How many screenshots to make '
                     f'(min={BhdTrackerConfig.defaults["screenshots"].min}, '
                     f'max={BhdTrackerConfig.defaults["screenshots"].max})'),
            'type': utils.argtypes.number_of_screenshots(BhdTrackerConfig),
        },
    }


@pytest.mark.asyncio
async def test_is_logged_in():
    tracker = BhdTracker()
    assert tracker.is_logged_in is True
    await tracker.login()
    assert tracker.is_logged_in is True
    await tracker.logout()
    assert tracker.is_logged_in is True


@pytest.mark.parametrize(
    argnames='announce_url',
    argvalues=(
        'http://bhd.tracker.local:1234/announce',
        'http://bhd.tracker.local:1234/announce/',
    ),
)
@pytest.mark.asyncio
async def test_get_announce_url(announce_url):
    tracker = BhdTracker(options={
        'announce_url': announce_url,
        'announce_passkey': 'd34db33f',
    })
    url = await tracker.get_announce_url()
    assert url == announce_url.rstrip('/') + '/d34db33f'


@pytest.mark.parametrize(
    argnames='upload_url',
    argvalues=(
        'http://bhd/upload',
        'http://bhd/upload/',
    ),
)
def test_get_upload_url(upload_url):
    tracker = BhdTracker(options={
        'upload_url': upload_url,
        'apikey': 'd34db33f',
    })
    url = tracker.get_upload_url()
    assert url == upload_url.rstrip('/') + '/d34db33f'


@pytest.mark.asyncio
async def test_upload_gets_invalid_json(mocker):
    tracker = BhdTracker(options={'upload_url': 'http://bhd.local/upload', 'apikey': '1337'})
    tracker_jobs_mock = Mock(
        post_data={'foo': 'bar'},
        torrent_filepath='path/to/content.torrent',
        mediainfo_filehandle=io.StringIO('mediainfo mock'),
    )
    http_mock = mocker.patch('upsies.utils.http', Mock(
        post=AsyncMock(return_value=Result(
            text='{choke on this',
            bytes=b'irrelevant',
        )),
    ))
    with pytest.raises(errors.RequestError, match=r'^Malformed JSON: \{choke on this'):
        await tracker.upload(tracker_jobs_mock)
    assert http_mock.post.call_args_list == [call(
        url='http://bhd.local/upload/1337',
        cache=False,
        user_agent=True,
        data=tracker_jobs_mock.post_data,
        files={
            'file': {
                'file': tracker_jobs_mock.torrent_filepath,
                'mimetype': 'application/octet-stream',
            },
            'mediainfo': {
                'file': tracker_jobs_mock.mediainfo_filehandle,
                'filename': 'mediainfo',
                'mimetype': 'application/octet-stream',
            },
        },
    )]

@pytest.mark.asyncio
async def test_upload_gets_error_status_code(mocker):
    tracker = BhdTracker(options={'upload_url': 'http://bhd.local/upload', 'apikey': '1337'})
    tracker_jobs_mock = Mock(
        post_data={'foo': 'bar'},
        torrent_filepath='path/to/content.torrent',
        mediainfo_filehandle=io.StringIO('mediainfo mock'),
    )
    http_mock = mocker.patch('upsies.utils.http', Mock(
        post=AsyncMock(return_value=Result(
            text='''
            {
                "status_code": 0,
                "success": false,
                "status_message": "This is the error message"
            }
            ''',
            bytes=b'irrelevant',
        )),
    ))
    with pytest.raises(errors.RequestError, match=r'^Upload failed: This is the error message$'):
        await tracker.upload(tracker_jobs_mock)
    assert http_mock.post.call_args_list == [call(
        url='http://bhd.local/upload/1337',
        cache=False,
        user_agent=True,
        data=tracker_jobs_mock.post_data,
        files={
            'file': {
                'file': tracker_jobs_mock.torrent_filepath,
                'mimetype': 'application/octet-stream',
            },
            'mediainfo': {
                'file': tracker_jobs_mock.mediainfo_filehandle,
                'filename': 'mediainfo',
                'mimetype': 'application/octet-stream',
            },
        },
    )]

@pytest.mark.asyncio
async def test_upload_gets_unexpected_status_code(mocker):
    tracker = BhdTracker(options={'upload_url': 'http://bhd.local/upload', 'apikey': '1337'})
    tracker_jobs_mock = Mock(
        post_data={'foo': 'bar'},
        torrent_filepath='path/to/content.torrent',
        mediainfo_filehandle=io.StringIO('mediainfo mock'),
    )
    http_mock = mocker.patch('upsies.utils.http', Mock(
        post=AsyncMock(return_value=Result(
            text='{"status_code": 123.5}',
            bytes=b'irrelevant',
        )),
    ))
    with pytest.raises(RuntimeError, match=r"^Unexpected response: '\{\"status_code\": 123.5\}'$"):
        await tracker.upload(tracker_jobs_mock)
    assert http_mock.post.call_args_list == [call(
        url='http://bhd.local/upload/1337',
        cache=False,
        user_agent=True,
        data=tracker_jobs_mock.post_data,
        files={
            'file': {
                'file': tracker_jobs_mock.torrent_filepath,
                'mimetype': 'application/octet-stream',
            },
            'mediainfo': {
                'file': tracker_jobs_mock.mediainfo_filehandle,
                'filename': 'mediainfo',
                'mimetype': 'application/octet-stream',
            },
        },
    )]

@pytest.mark.asyncio
async def test_upload_gets_unexpected_json(mocker):
    tracker = BhdTracker(options={'upload_url': 'http://bhd.local/upload', 'apikey': '1337'})
    tracker_jobs_mock = Mock(
        post_data={'foo': 'bar'},
        torrent_filepath='path/to/content.torrent',
        mediainfo_filehandle=io.StringIO('mediainfo mock'),
    )
    http_mock = mocker.patch('upsies.utils.http', Mock(
        post=AsyncMock(return_value=Result(
            text='{"hey": "you"}',
            bytes=b'irrelevant',
        )),
    ))
    with pytest.raises(RuntimeError, match=r"^Unexpected response: '\{\"hey\": \"you\"\}'$"):
        await tracker.upload(tracker_jobs_mock)
    assert http_mock.post.call_args_list == [call(
        url='http://bhd.local/upload/1337',
        cache=False,
        user_agent=True,
        data=tracker_jobs_mock.post_data,
        files={
            'file': {
                'file': tracker_jobs_mock.torrent_filepath,
                'mimetype': 'application/octet-stream',
            },
            'mediainfo': {
                'file': tracker_jobs_mock.mediainfo_filehandle,
                'filename': 'mediainfo',
                'mimetype': 'application/octet-stream',
            },
        },
    )]

@pytest.mark.asyncio
async def test_upload_succeeds(mocker):
    tracker = BhdTracker(options={'upload_url': 'http://bhd.local/upload', 'apikey': '1337'})
    tracker_jobs_mock = Mock(
        post_data={
            'foo': 'asdf',
            'bar': '',
            'baz': 0,
            'quux': '0',
            'quuz': None,
        },
        torrent_filepath='path/to/content.torrent',
        mediainfo_filehandle=io.StringIO('mediainfo mock'),
    )
    http_mock = mocker.patch('upsies.utils.http', Mock(
        post=AsyncMock(return_value=Result(
            text='''
            {
                "status_code": 2,
                "success": true,
                "status_message": "http://bhd.local/torrent/download/release_name.123456.d34db33f"
            }
            ''',
            bytes=b'irrelevant',
        )),
    ))
    torrent_page_url = await tracker.upload(tracker_jobs_mock)
    assert torrent_page_url == 'http://bhd.local/torrents/release_name.123456'
    assert http_mock.post.call_args_list == [call(
        url='http://bhd.local/upload/1337',
        cache=False,
        user_agent=True,
        data={
            'foo': 'asdf',
            'baz': '0',
            'quux': '0',
        },
        files={
            'file': {
                'file': tracker_jobs_mock.torrent_filepath,
                'mimetype': 'application/octet-stream',
            },
            'mediainfo': {
                'file': tracker_jobs_mock.mediainfo_filehandle,
                'filename': 'mediainfo',
                'mimetype': 'application/octet-stream',
            },
        },
    )]

@pytest.mark.asyncio
async def test_upload_draft_succeeds(mocker):
    tracker = BhdTracker(options={'upload_url': 'http://bhd.local/upload', 'apikey': '1337'})
    warning_cb = Mock()
    tracker.signal.register('warning', warning_cb)
    tracker_jobs_mock = Mock(
        post_data={'foo': 'bar'},
        torrent_filepath='path/to/content.torrent',
        mediainfo_filehandle=io.StringIO('mediainfo mock'),
    )
    http_mock = mocker.patch('upsies.utils.http', Mock(
        post=AsyncMock(return_value=Result(
            text='''
            {
                "status_code": 1,
                "success": true,
                "status_message": "Draft uploaded"
            }
            ''',
            bytes=b'irrelevant',
        )),
    ))
    torrent_filepath = await tracker.upload(tracker_jobs_mock)
    assert warning_cb.call_args_list == [
        call('Draft uploaded'),
        call('You have to activate your upload manually '
             'on the website when you are ready to seed.')
    ]
    assert torrent_filepath == tracker_jobs_mock.torrent_filepath
    assert http_mock.post.call_args_list == [call(
        url='http://bhd.local/upload/1337',
        cache=False,
        user_agent=True,
        data=tracker_jobs_mock.post_data,
        files={
            'file': {
                'file': tracker_jobs_mock.torrent_filepath,
                'mimetype': 'application/octet-stream',
            },
            'mediainfo': {
                'file': tracker_jobs_mock.mediainfo_filehandle,
                'filename': 'mediainfo',
                'mimetype': 'application/octet-stream',
            },
        },
    )]
