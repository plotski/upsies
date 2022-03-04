import base64
import os
import re
from unittest.mock import Mock, PropertyMock, call

import aiobtclientrpc
import pytest

from upsies import errors
from upsies.utils.btclients import transmission


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_name(tmp_path):
    assert transmission.TransmissionClientApi.name == 'transmission'


def test_label(tmp_path):
    assert transmission.TransmissionClientApi.label == 'Transmission'


def test_default_config(tmp_path):
    assert transmission.TransmissionClientApi.default_config == {
        'url': 'http://localhost:9091/transmission/rpc',
        'username': '',
        'password': '',
    }


def test_rpc(mocker):
    TransmissionRPC_mock = mocker.patch('aiobtclientrpc.TransmissionRPC', Mock())
    api = transmission.TransmissionClientApi()
    rpc = api._rpc
    assert rpc is TransmissionRPC_mock.return_value
    assert TransmissionRPC_mock.call_args_list == [call(
        url=api.config['url'],
        username=api.config['username'],
        password=api.config['password'],
    )]
    assert rpc is api._rpc  # Singleton property


@pytest.mark.asyncio
async def test_add_torrent_fails_to_read_torrent_file(mocker):
    api = transmission.TransmissionClientApi()

    mocker.patch.object(api, 'read_torrent_file', Mock(
        side_effect=errors.TorrentError('Unable to read'),
    ))
    mocker.patch.object(type(api), '_rpc', PropertyMock(
        return_value="This is not an async context manager, but I don't care.",
    ))

    with pytest.raises(errors.RequestError, match=r'^Unable to read$'):
        await api.add_torrent(torrent_path='file.torrent')

    assert api.read_torrent_file.call_args_list == [call('file.torrent')]

@pytest.mark.parametrize('download_path', (None, '', '/absolute/path', 'relative/path'))
@pytest.mark.asyncio
async def test_add_torrent_calls_rpc_method(download_path, mocker):
    api = transmission.TransmissionClientApi()

    mocker.patch.object(api, 'read_torrent_file', Mock(return_value=b'torrent metainfo'))
    mocker.patch.object(type(api), '_rpc', PropertyMock(
        return_value=Mock(
            __aenter__=AsyncMock(),
            # Return False to indicate exception must propagate
            __aexit__=AsyncMock(return_value=False),
            call=AsyncMock(
                return_value={
                    'arguments': {'torrent-added': {'hashString': 'DE4DB33F'}},
                    'result': 'success',
                },
            ),
        ),
    ))

    torrent_hash = await api.add_torrent(
        torrent_path='file.torrent',
        download_path=download_path,
    )
    assert torrent_hash == 'DE4DB33F'
    assert api.read_torrent_file.call_args_list == [call('file.torrent')]
    if download_path:
        assert api._rpc.call.call_args_list == [call(
            'torrent-add',
            {
                'metainfo': base64.b64encode(b'torrent metainfo').decode('ascii'),
                'download-dir': os.path.abspath(download_path),
            },
        )]
    else:
        assert api._rpc.call.call_args_list == [call(
            'torrent-add',
            {
                'metainfo': base64.b64encode(b'torrent metainfo').decode('ascii'),
            },
        )]


@pytest.mark.parametrize(
    argnames='exception',
    argvalues=(
        aiobtclientrpc.ConnectionError('no connection'),
        aiobtclientrpc.AuthenticationError('authentication failed'),
        aiobtclientrpc.TimeoutError('timeout'),
        aiobtclientrpc.ValueError('invalid value'),
        aiobtclientrpc.RPCError('wat'),
    ),
    ids=lambda v: repr(v),
)
@pytest.mark.asyncio
async def test_add_torrent_catches_error_from_rpc_method_call(exception, mocker):
    api = transmission.TransmissionClientApi()

    mocker.patch.object(api, 'read_torrent_file', Mock(return_value=b'torrent metainfo'))
    mocker.patch.object(type(api), '_rpc', PropertyMock(
        return_value=Mock(
            __aenter__=AsyncMock(),
            # Return False to indicate exception must propagate
            __aexit__=AsyncMock(return_value=False),
            call=AsyncMock(side_effect=exception),
        ),
    ))

    with pytest.raises(errors.RequestError, match=rf'^{re.escape(str(exception))}$'):
        await api.add_torrent(torrent_path='file.torrent')

    assert api.read_torrent_file.call_args_list == [call('file.torrent')]
    assert api._rpc.call.call_args_list == [call(
        'torrent-add',
        {'metainfo': base64.b64encode(b'torrent metainfo').decode('ascii')},
    )]


@pytest.mark.parametrize(
    argnames='response, exp_return_value, exp_exception',
    argvalues=(
        ({'arguments': {'torrent-added': {'hashString': 'd34db33f'}}}, 'd34db33f', None),
        ({'arguments': {'torrent-duplicate': {'hashString': 'd34db33f'}}}, 'd34db33f', None),
        ({'arguments': {}}, None, RuntimeError('Unexpected response: ' + repr({'arguments': {}}))),
        ({'foo': 123}, None, RuntimeError('Unexpected response: ' + repr({'foo': 123}))),
    ),
    ids=lambda v: repr(v),
)
@pytest.mark.asyncio
async def test_add_torrent_reads_response(response, exp_return_value, exp_exception, mocker):
    api = transmission.TransmissionClientApi()

    mocker.patch.object(api, 'read_torrent_file', Mock(return_value=b'torrent metainfo'))
    mocker.patch.object(type(api), '_rpc', PropertyMock(
        return_value=Mock(
            __aenter__=AsyncMock(),
            # Return False to indicate exception must propagate
            __aexit__=AsyncMock(return_value=False),
            call=AsyncMock(return_value=response),
        ),
    ))

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await api.add_torrent(torrent_path='file.torrent')
    else:
        return_value = await api.add_torrent(torrent_path='file.torrent')
        assert return_value == exp_return_value
