import re
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.trackers import nbl
from upsies.utils.http import Result


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_name_attribute():
    assert nbl.NblTracker.name == 'nbl'


def test_label_attribute():
    assert nbl.NblTracker.label == 'NBL'


@pytest.mark.asyncio
async def test_login_logout(mocker):
    tracker = nbl.NblTracker(options={})
    assert tracker.is_logged_in is True
    await tracker.login()
    assert tracker.is_logged_in is True
    await tracker.logout()
    assert tracker.is_logged_in is True


@pytest.mark.asyncio
async def test_get_announce_url(mocker):
    tracker = nbl.NblTracker(options={'announce_url': 'https://nbl.local:123/d34db33f/announce'})
    announce_url = await tracker.get_announce_url()
    assert announce_url == 'https://nbl.local:123/d34db33f/announce'


def test_get_upload_url(mocker):
    tracker = nbl.NblTracker(options={'upload_url': 'https://nbl.local/upload'})
    upload_url = tracker.get_upload_url()
    assert upload_url == 'https://nbl.local/upload'


@pytest.mark.asyncio
async def test_upload_without_api_key(mocker):
    tracker = nbl.NblTracker(
        options={
            'apikey': '',
            'upload_url': 'http://nbl.local/upload',
            'announce': 'http://nbl.local/announce',
        },
    )
    http_mock = mocker.patch('upsies.utils.http', Mock(
        get=AsyncMock(),
        post=AsyncMock(),
    ))
    get_upload_url_mock = mocker.patch.object(tracker, 'get_upload_url')
    tracker_jobs_mock = Mock()

    with pytest.raises(errors.RequestError, match=r'^No API key configured$'):
        await tracker.upload(tracker_jobs_mock)

    assert get_upload_url_mock.call_args_list == []
    assert http_mock.get.call_args_list == []
    assert http_mock.post.call_args_list == []


@pytest.mark.asyncio
async def test_upload_succeeds(mocker):
    tracker = nbl.NblTracker(options={'apikey': 'thisismyapikey'})
    http_mock = mocker.patch('upsies.trackers.nbl.tracker.http', Mock(
        get=AsyncMock(),
        post=AsyncMock(return_value=Result(
            text='''
            {
                "status": "success"
            }
            ''',
            bytes=b'irrelevant',
        )),
    ))
    mocker.patch.object(tracker, 'get_upload_url', return_value='http://upload.url')
    tracker_jobs_mock = Mock(
        post_data={
            'one': 'Hello',
            'two': '',
            'three': 123,
            'four': None,
            'five': 'World',
        },
        torrent_filepath='path/to/file.torrent',
    )

    return_value = await tracker.upload(tracker_jobs_mock)
    assert return_value == tracker_jobs_mock.torrent_filepath

    assert http_mock.get.call_args_list == []
    assert http_mock.post.call_args_list == [call(
        url='http://upload.url',
        cache=False,
        user_agent=True,
        data={
            'one': 'Hello',
            'three': '123',
            'five': 'World',
        },
        files={
            'file_input': {
                'file': 'path/to/file.torrent',
                'mimetype': 'application/x-bittorrent',
            },
        },
    )]


@pytest.mark.parametrize(
    argnames='response, exp_exception',
    argvalues=(
        (Result(text='{"status": "success"}', bytes=b'irrelevant'),
         None),
        (Result(text='{"status": "success?"}', bytes=b'irrelevant'),
         RuntimeError("Unexpected response: {'status': 'success?'}")),

        # NOTE: We expect error messages as JSON in error responses
        #       (RequestError) and success responses (Result).

        (errors.RequestError(msg='irrelevant', text='{"message": "Maybe!"}'),
         errors.RequestError('Upload failed: Maybe!')),
        (Result(text='{"message": "Maybe!"}', bytes=b'irrelevant'),
         errors.RequestError('Upload failed: Maybe!')),

        (errors.RequestError(msg='irrelevant', text='{"error": "No!"}'),
         errors.RequestError('Upload failed: No!')),
        (Result(text='{"error": "No!"}', bytes=b'irrelevant'),
         errors.RequestError('Upload failed: No!')),

        (errors.RequestError(msg='irrelevant', text='{"invalid": json]'),
         errors.RequestError('Upload failed: {"invalid": json]')),
        (Result(text='{"invalid": json]', bytes=b'irrelevant'),
         errors.RequestError('Malformed JSON: {"invalid": json]: Expecting value: line 1 column 13 (char 12)')),

        (errors.RequestError(msg='irrelevant', text='{"foo": "Bar!"}'),
         RuntimeError("Unexpected response: {'foo': 'Bar!'}")),
        (Result(text='{"foo": "Bar!"}', bytes=b'irrelevant'),
         RuntimeError("Unexpected response: {'foo': 'Bar!'}")),
    ),
)
@pytest.mark.asyncio
async def test_upload_handles_errors(response, exp_exception, mocker):
    tracker = nbl.NblTracker(options={'apikey': 'thisismyapikey'})
    upload_url = 'http://mock.url/upload.php'
    http_mock = mocker.patch('upsies.trackers.nbl.tracker.http', Mock(
        get=AsyncMock(),
        post=AsyncMock(),
    ))
    if isinstance(response, Exception):
        http_mock.post.side_effect = response
    else:
        http_mock.post.return_value = response
    mocker.patch.object(tracker, 'get_upload_url', return_value=upload_url)
    tracker_jobs_mock = Mock(
        post_data={'one': 'Hello', 'two': 'World'},
        torrent_filepath='path/to/file.torrent',
    )

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await tracker.upload(tracker_jobs_mock)
    else:
        return_value = await tracker.upload(tracker_jobs_mock)
        assert return_value is tracker_jobs_mock.torrent_filepath

    assert http_mock.get.call_args_list == []
    assert http_mock.post.call_args_list == [call(
        url=upload_url,
        cache=False,
        user_agent=True,
        data={
            'one': 'Hello',
            'two': 'World',
        },
        files={
            'file_input': {
                'file': 'path/to/file.torrent',
                'mimetype': 'application/x-bittorrent',
            },
        },
    )]
