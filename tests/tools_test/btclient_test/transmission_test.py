import base64
import json
import re
from unittest.mock import Mock, call, patch

import aiohttp
import aiohttp.test_utils
import pytest

from upsies import errors
from upsies.tools.btclient import transmission


def test_name(tmp_path):
    assert transmission.ClientApi.name == 'transmission'


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


class MockDaemon(aiohttp.test_utils.TestServer):
    def __init__(self, responses):
        super().__init__(aiohttp.web.Application())
        self.requests_seen = []
        self._csrf_token = 'random CSRF token'
        self.app.router.add_route('post', '/transmission/rpc', self.rpc)
        self.responses = list(responses)

    async def rpc(self, request):
        self.requests_seen.append({
            'method': request.method,
            'csrf_token': request.headers.get(transmission.CSRF_HEADER, None),
            'text': await request.text(),
        })
        return self.responses.pop(0)

@pytest.mark.asyncio
async def test_CSRF_token():
    response = {'argument': 'OK', 'result': 'success'}
    srv_cm = MockDaemon(responses=(
        aiohttp.web.Response(
            status=transmission.CSRF_ERROR_CODE,
            headers={transmission.CSRF_HEADER: 'random string'},
        ),
        aiohttp.web.json_response(response),
    ))
    async with srv_cm as srv:
        api = transmission.ClientApi(
            url=f'http://localhost:{srv.port}/transmission/rpc',
        )
        assert await api._request('request data') == response
        assert srv.requests_seen == [
            {'method': 'POST', 'csrf_token': None, 'text': 'request data'},
            {'method': 'POST', 'csrf_token': 'random string', 'text': 'request data'},
        ]

@pytest.mark.asyncio
async def test_authentication_fails():
    srv_cm = MockDaemon(responses=(
        aiohttp.web.Response(status=transmission.AUTH_ERROR_CODE),
    ))
    async with srv_cm as srv:
        api = transmission.ClientApi(
            url=f'http://localhost:{srv.port}/transmission/rpc',
            username='foo',
            password='bar',
        )
        with pytest.raises(errors.TorrentError, match='^Authentication failed$'):
            await api._request('request data')
        assert srv.requests_seen == [
            {'method': 'POST', 'csrf_token': None, 'text': 'request data'},
        ]

@pytest.mark.asyncio
async def test_connection_refused():
    url = f'http://localhost:{aiohttp.test_utils.unused_port()}/transmission/rpc'
    api = transmission.ClientApi(
        url=url,
        username='foo',
        password='bar',
    )
    with pytest.raises(errors.TorrentError, match=f'^{re.escape(url)}: Failed to connect$'):
        await api._request('request data')

@pytest.mark.asyncio
async def test_response_is_not_json():
    srv_cm = MockDaemon(responses=(
        aiohttp.web.Response(text='this is not json'),
    ))
    async with srv_cm as srv:
        api = transmission.ClientApi(
            url=f'http://localhost:{srv.port}/transmission/rpc',
        )
        with pytest.raises(errors.TorrentError, match='^Malformed JSON response: this is not json$'):
            await api._request('request data')
        assert srv.requests_seen == [
            {'method': 'POST', 'csrf_token': None, 'text': 'request data'},
        ]


@pytest.mark.asyncio
async def test_add_torrent_with_download_path_argument():
    response = {
        'arguments': {'torrent-added': {'id': 1234}},
        'result': 'success',
    }
    api = transmission.ClientApi()
    request_mock = AsyncMock(return_value=response)
    read_torrent_file_mock = Mock(return_value=b'torrent metainfo')
    with patch.multiple(api, _request=request_mock, read_torrent_file=read_torrent_file_mock):
        torrent_id = await api.add_torrent('file.torrent', '/path/to/file')
        assert torrent_id == 1234
        assert read_torrent_file_mock.call_args_list == [call('file.torrent')]
        assert request_mock.call_args_list == [call(
            json.dumps({
                'method' : 'torrent-add',
                'arguments' : {
                    'metainfo': str(base64.b64encode(b'torrent metainfo'), encoding='ascii'),
                    'download-dir': '/path/to/file',
                },
            })
        )]

@pytest.mark.asyncio
async def test_add_torrent_without_download_path_argument():
    response = {
        'arguments': {'torrent-added': {'id': 1234}},
        'result': 'success',
    }
    api = transmission.ClientApi()
    request_mock = AsyncMock(return_value=response)
    read_torrent_file_mock = Mock(return_value=b'torrent metainfo')
    with patch.multiple(api, _request=request_mock, read_torrent_file=read_torrent_file_mock):
        torrent_id = await api.add_torrent('file.torrent')
        assert torrent_id == 1234
        assert read_torrent_file_mock.call_args_list == [call('file.torrent')]
        assert request_mock.call_args_list == [call(
            json.dumps({
                'method' : 'torrent-add',
                'arguments' : {
                    'metainfo': str(base64.b64encode(b'torrent metainfo'), encoding='ascii'),
                },
            })
        )]

@pytest.mark.asyncio
async def test_add_torrent_ignores_existing_torrent():
    response = {
        'arguments': {'torrent-added': {'id': 'abcd'}},
        'result': 'success',
    }
    api = transmission.ClientApi()
    request_mock = AsyncMock(return_value=response)
    read_torrent_file_mock = Mock(return_value=b'torrent metainfo')
    with patch.multiple(api, _request=request_mock, read_torrent_file=read_torrent_file_mock):
        torrent_id = await api.add_torrent('file.torrent', '/path/to/file')
        assert torrent_id == 'abcd'
        assert read_torrent_file_mock.call_args_list == [call('file.torrent')]
        assert request_mock.call_args_list == [call(
            json.dumps({
                'method' : 'torrent-add',
                'arguments' : {
                    'metainfo': str(base64.b64encode(b'torrent metainfo'), encoding='ascii'),
                    'download-dir': '/path/to/file',
                },
            })
        )]

@pytest.mark.asyncio
async def test_add_torrent_uses_result_field_as_error_message():
    response = {
        'arguments': {},
        'result': 'Klonk',
    }
    api = transmission.ClientApi()
    request_mock = AsyncMock(return_value=response)
    read_torrent_file_mock = Mock(return_value=b'torrent metainfo')
    with patch.multiple(api, _request=request_mock, read_torrent_file=read_torrent_file_mock):
        with pytest.raises(errors.TorrentError, match=r'^Klonk$'):
            await api.add_torrent('file.torrent', '/path/to/file')
        assert read_torrent_file_mock.call_args_list == [call('file.torrent')]
        assert request_mock.call_args_list == [call(
            json.dumps({
                'method' : 'torrent-add',
                'arguments' : {
                    'metainfo': str(base64.b64encode(b'torrent metainfo'), encoding='ascii'),
                    'download-dir': '/path/to/file',
                },
            })
        )]

@pytest.mark.asyncio
async def test_add_torrent_reports_generic_error():
    response = {}
    api = transmission.ClientApi()
    request_mock = AsyncMock(return_value=response)
    read_torrent_file_mock = Mock(return_value=b'torrent metainfo')
    with patch.multiple(api, _request=request_mock, read_torrent_file=read_torrent_file_mock):
        with pytest.raises(errors.TorrentError, match=r'^Adding failed for unknown reason$'):
            await api.add_torrent('file.torrent', '/path/to/file')
        assert read_torrent_file_mock.call_args_list == [call('file.torrent')]
        assert request_mock.call_args_list == [call(
            json.dumps({
                'method' : 'torrent-add',
                'arguments' : {
                    'metainfo': str(base64.b64encode(b'torrent metainfo'), encoding='ascii'),
                    'download-dir': '/path/to/file',
                },
            })
        )]
