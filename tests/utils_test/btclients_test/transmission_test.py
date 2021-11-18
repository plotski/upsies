import base64
import json
import os
import re
from unittest.mock import Mock, call

import pytest
from pytest_httpserver.httpserver import Response

from upsies import errors
from upsies.utils.btclients import transmission


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


class RequestHandler:
    def __init__(self):
        self.requests_seen = []

    def __call__(self, request):
        # `request` is a Request object from werkzeug
        # https://werkzeug.palletsprojects.com/en/1.0.x/wrappers/#werkzeug.wrappers.BaseRequest
        try:
            return self.handle(request)
        except Exception as e:
            # pytest-httpserver doesn't show the traceback if we call
            # raise_for_status() on the response.
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
            raise

    def handle(self, request):
        raise NotImplementedError()


def test_name(tmp_path):
    assert transmission.TransmissionClientApi.name == 'transmission'


@pytest.mark.asyncio
async def test_request_connection_error():
    url = 'http://localhost:12345/'
    api = transmission.TransmissionClientApi(config={'url': url})
    with pytest.raises(errors.RequestError, match=f'^{re.escape(url)}: All connection attempts failed'):
        await api._request('foo')

@pytest.mark.asyncio
async def test_request_json_parsing_error(httpserver):
    path = '/transmission/rpc'
    httpserver.expect_request(uri=path).respond_with_data('this is not json')
    url = httpserver.url_for(path)
    api = transmission.TransmissionClientApi(config={'url': url})
    with pytest.raises(errors.RequestError, match='^Malformed JSON: this is not json: '):
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
                status=transmission.TransmissionClientApi.CSRF_ERROR_CODE,
                headers={transmission.TransmissionClientApi.CSRF_HEADER: csrf_token},
            ),
            json.dumps(response),
        ]

        def handle(self, request):
            self.requests_seen.append({
                'method': request.method,
                'csrf_token': request.headers.get(transmission.TransmissionClientApi.CSRF_HEADER),
                'data': request.data,
            })
            return self.responses.pop(0)

    handler = Handler()
    httpserver.expect_request(uri=path).respond_with_handler(handler)

    api = transmission.TransmissionClientApi(config={'url': httpserver.url_for(path)})
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
    api = transmission.TransmissionClientApi(config={
        'url': httpserver.url_for(path),
        'username': 'foo',
        'password': 'bar',
    })
    assert await api._request('request data') == {'response': 'info'}

@pytest.mark.asyncio
async def test_request_authentication_fails(httpserver):
    path = '/transmission/rpc'
    httpserver.expect_request(uri=path).respond_with_data(
        status=transmission.TransmissionClientApi.AUTH_ERROR_CODE,
    )
    api = transmission.TransmissionClientApi(config={'url': httpserver.url_for(path)})
    with pytest.raises(errors.RequestError, match='^Authentication failed$'):
        await api._request('request data')


@pytest.mark.asyncio
async def test_add_torrent_fails_to_read_torrent_file(mocker):
    api = transmission.TransmissionClientApi()
    mocker.patch.multiple(
        api,
        _request=AsyncMock(),
        read_torrent_file=Mock(side_effect=errors.TorrentError('Unable to read')),
    )
    with pytest.raises(errors.RequestError, match=r'^Unable to read$'):
        await api.add_torrent(torrent_path='file.torrent')
    assert api.read_torrent_file.call_args_list == [call('file.torrent')]
    assert api._request.call_args_list == []

@pytest.mark.parametrize(
    argnames='torrent_added_field',
    argvalues=('torrent-added', 'torrent-duplicate'),
)
@pytest.mark.asyncio
async def test_add_torrent_with_download_path_argument(torrent_added_field, mocker):
    response = {
        'arguments': {torrent_added_field: {'hashString': 'DE4DB33F'}},
        'result': 'success',
    }
    api = transmission.TransmissionClientApi()
    mocker.patch.multiple(
        api,
        _request=AsyncMock(return_value=response),
        read_torrent_file=Mock(return_value=b'torrent metainfo'),
    )
    torrent_hash = await api.add_torrent(
        torrent_path='file.torrent',
        download_path='/path/to/file',
    )
    assert torrent_hash == 'DE4DB33F'
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
        'arguments': {torrent_added_field: {'hashString': 'DE4DB33F'}},
        'result': 'success',
    }
    api = transmission.TransmissionClientApi()
    mocker.patch.multiple(
        api,
        _request=AsyncMock(return_value=response),
        read_torrent_file=Mock(return_value=b'torrent metainfo'),
    )
    torrent_hash = await api.add_torrent(
        torrent_path='file.torrent',
    )
    assert torrent_hash == 'DE4DB33F'
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
async def test_add_torrent_with_relative_download_path_argument(mocker):
    response = {
        'arguments': {'torrent-added': {'hashString': 'DE4DB33F'}},
        'result': 'success',
    }
    api = transmission.TransmissionClientApi()
    mocker.patch.multiple(
        api,
        _request=AsyncMock(return_value=response),
        read_torrent_file=Mock(return_value=b'torrent metainfo'),
    )
    torrent_hash = await api.add_torrent(
        torrent_path='file.torrent',
        download_path='relative/path',
    )
    assert torrent_hash == 'DE4DB33F'
    assert api.read_torrent_file.call_args_list == [call('file.torrent')]
    assert api._request.call_args_list == [call(
        json.dumps({
            'method' : 'torrent-add',
            'arguments' : {
                'metainfo': base64.b64encode(b'torrent metainfo').decode('ascii'),
                'download-dir': os.path.abspath('relative/path'),
            },
        })
    )]

@pytest.mark.asyncio
async def test_add_torrent_uses_result_field_as_error_message(mocker):
    response = {
        'arguments': {},
        'result': 'Kaboom!',
    }
    api = transmission.TransmissionClientApi()
    mocker.patch.multiple(
        api,
        _request=AsyncMock(return_value=response),
        read_torrent_file=Mock(return_value=b'torrent metainfo'),
    )
    with pytest.raises(errors.RequestError, match=r'^Kaboom!$'):
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
    api = transmission.TransmissionClientApi()
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
