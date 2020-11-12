import asyncio
import base64
import json
import re
import traceback
from unittest.mock import Mock, call

import pytest
from pytest_httpserver.httpserver import Response

from upsies import errors
from upsies.tools.btclient import transmission

# httpx.AsyncClient() must be closed before the process terminates. We need a
# loop for that. By default, pytest-asyncio uses a new loop for every test. By
# overloading the event_loop fixture, we use one AsyncClient instance for every
# test in this module and close it after all tests ran.
@pytest.fixture(scope='module')
def event_loop():
    from upsies.utils import http
    http._client = type(http._client)()
    loop = asyncio.new_event_loop()
    yield loop
    loop.run_until_complete(http._client.aclose())
    loop.close()


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


class RequestHandler:
    def __init__(self):
        self.requests_seen = []

    def __call__(self, request):
        try:
            return self.handle(request)
        except Exception as e:
            # pytest-httpserver doesn't show the traceback if we call
            # raise_for_status() on the response.
            traceback.print_exception(type(e), e, e.__traceback__)
            raise

    def handle(self, request):
        raise NotImplementedError()


def test_name(tmp_path):
    assert transmission.ClientApi.name == 'transmission'


@pytest.mark.asyncio
async def test_request_connection_error():
    url = 'http://localhost:12345/'
    api = transmission.ClientApi(url=url)
    with pytest.raises(errors.TorrentError, match=f'^{re.escape(url)}: Failed to connect$'):
        await api._request('foo')

@pytest.mark.asyncio
async def test_request_json_parsing_error(httpserver):
    path = '/transmission/rpc'
    httpserver.expect_request(uri=path).respond_with_data('this is not json')
    url = httpserver.url_for(path)
    api = transmission.ClientApi(url=url)
    with pytest.raises(errors.TorrentError, match='^Malformed JSON: this is not json: '):
        await api._request('foo')

@pytest.mark.asyncio
async def test_request_CSRF_token(httpserver):
    path = '/transmission/rpc'
    data = b'request data'
    response = {'argument': 'OK', 'result': 'success'}
    csrf_token = 'random string'

    class Handler(RequestHandler):
        responses = [
            Response(
                status=transmission.CSRF_ERROR_CODE,
                headers={transmission.CSRF_HEADER: csrf_token},
            ),
            json.dumps(response),
        ]

        def handle(self, request):
            self.requests_seen.append({
                'method': request.method,
                'csrf_token': request.headers.get(transmission.CSRF_HEADER),
                'data': request.data,
            })
            return self.responses.pop(0)

    handler = Handler()
    httpserver.expect_request(uri=path).respond_with_handler(handler)

    api = transmission.ClientApi(url=httpserver.url_for(path))
    assert await api._request(data) == response
    assert handler.requests_seen == [
        {'method': 'POST', 'csrf_token': None, 'data': data},
        {'method': 'POST', 'csrf_token': csrf_token, 'data': data},
    ]

@pytest.mark.asyncio
async def test_request_authentication_credentials_are_sent(httpserver):
    path = '/transmission/rpc'
    auth = ('foo', 'bar')
    auth_bytes = bytes(':'.join(auth), encoding='ascii')
    auth_encoded = base64.b64encode(auth_bytes).decode('ascii')
    httpserver.expect_request(
        uri=path,
        headers={'Authorization': f'Basic {auth_encoded}'},
    ).respond_with_json(
        {'response': 'info'}
    )
    api = transmission.ClientApi(
        url=httpserver.url_for(path),
        username='foo',
        password='bar',
    )
    assert await api._request('request data') == {'response': 'info'}

@pytest.mark.asyncio
async def test_request_authentication_fails(httpserver):
    path = '/transmission/rpc'
    httpserver.expect_request(uri=path).respond_with_data(
        status=transmission.AUTH_ERROR_CODE,
    )
    api = transmission.ClientApi(url=httpserver.url_for(path))
    with pytest.raises(errors.TorrentError, match='^Authentication failed$'):
        await api._request('request data')


@pytest.mark.parametrize(
    argnames='torrent_added_field',
    argvalues=('torrent-added', 'torrent-duplicate'),
)
@pytest.mark.asyncio
async def test_add_torrent_with_download_path_argument(torrent_added_field, mocker):
    response = {
        'arguments': {torrent_added_field: {'id': 1234}},
        'result': 'success',
    }
    api = transmission.ClientApi()
    mocker.patch.multiple(
        api,
        _request=AsyncMock(return_value=response),
        read_torrent_file=Mock(return_value=b'torrent metainfo'),
    )
    torrent_id = await api.add_torrent(
        torrent_path='file.torrent',
        download_path='/path/to/file',
    )
    assert torrent_id == 1234
    assert api.read_torrent_file.call_args_list == [call('file.torrent')]
    assert api._request.call_args_list == [call(
        json.dumps({
            'method' : 'torrent-add',
            'arguments' : {
                'metainfo': base64.b64encode(b'torrent metainfo').decode('ascii'),
                'download-dir': '/path/to/file',
            },
        })
    )]

@pytest.mark.parametrize(
    argnames='torrent_added_field',
    argvalues=('torrent-added', 'torrent-duplicate'),
)
@pytest.mark.asyncio
async def test_add_torrent_without_download_path_argument(torrent_added_field, mocker):
    response = {
        'arguments': {torrent_added_field: {'id': 1234}},
        'result': 'success',
    }
    api = transmission.ClientApi()
    mocker.patch.multiple(
        api,
        _request=AsyncMock(return_value=response),
        read_torrent_file=Mock(return_value=b'torrent metainfo'),
    )
    torrent_id = await api.add_torrent(
        torrent_path='file.torrent',
    )
    assert torrent_id == 1234
    assert api.read_torrent_file.call_args_list == [call('file.torrent')]
    assert api._request.call_args_list == [call(
        json.dumps({
            'method' : 'torrent-add',
            'arguments' : {
                'metainfo': base64.b64encode(b'torrent metainfo').decode('ascii'),
            },
        })
    )]

@pytest.mark.asyncio
async def test_add_torrent_uses_result_field_as_error_message(mocker):
    response = {
        'arguments': {},
        'result': 'Kaboom!',
    }
    api = transmission.ClientApi()
    mocker.patch.multiple(
        api,
        _request=AsyncMock(return_value=response),
        read_torrent_file=Mock(return_value=b'torrent metainfo'),
    )
    with pytest.raises(errors.TorrentError, match=r'^Kaboom!$'):
        await api.add_torrent('file.torrent')
    assert api.read_torrent_file.call_args_list == [call('file.torrent')]
    assert api._request.call_args_list == [call(
        json.dumps({
            'method' : 'torrent-add',
            'arguments' : {
                'metainfo': base64.b64encode(b'torrent metainfo').decode('ascii'),
            },
        })
    )]

@pytest.mark.asyncio
async def test_add_torrent_reports_generic_error(mocker):
    response = {'something': 'unexpected'}
    api = transmission.ClientApi()
    mocker.patch.multiple(
        api,
        _request=AsyncMock(return_value=response),
        read_torrent_file=Mock(return_value=b'torrent metainfo'),
    )
    with pytest.raises(RuntimeError, match=(r'^Unexpected response: '
                                            + re.escape("{'something': 'unexpected'}"))):
        await api.add_torrent('file.torrent')
    assert api.read_torrent_file.call_args_list == [call('file.torrent')]
    assert api._request.call_args_list == [call(
        json.dumps({
            'method' : 'torrent-add',
            'arguments' : {
                'metainfo': base64.b64encode(b'torrent metainfo').decode('ascii'),
            },
        })
    )]
