import base64
import os
import re
import sys
from unittest.mock import Mock, PropertyMock, call

import aiobtclientrpc
import pytest

from upsies import errors
from upsies.utils.btclients import deluge


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_name(tmp_path):
    assert deluge.DelugeClientApi.name == 'deluge'


def test_label(tmp_path):
    assert deluge.DelugeClientApi.label == 'Deluge'


def test_default_config(tmp_path):
    assert deluge.DelugeClientApi.default_config == {
        'url': '127.0.0.1:58846',
        'username': '',
        'password': '',
        'check_after_add': False,
    }


def test_rpc(mocker):
    DelugeRPC_mock = mocker.patch('aiobtclientrpc.DelugeRPC', Mock())
    api = deluge.DelugeClientApi()
    rpc = api._rpc
    assert rpc is DelugeRPC_mock.return_value
    assert DelugeRPC_mock.call_args_list == [call(
        url=api.config['url'],
        username=api.config['username'],
        password=api.config['password'],
    )]
    assert rpc is api._rpc  # Singleton property


@pytest.mark.asyncio
async def test_add_torrent_fails_to_read_torrent_file(mocker):
    api = deluge.DelugeClientApi()

    mocker.patch.object(api, 'read_torrent_file', Mock(
        side_effect=errors.TorrentError('Unable to read'),
    ))
    mocker.patch.object(type(api), '_rpc', PropertyMock(
        return_value="This is not an async context manager, but I don't care.",
    ))

    with pytest.raises(errors.RequestError, match=r'^Unable to read$'):
        await api.add_torrent(torrent_path='file.torrent')

    assert api.read_torrent_file.call_args_list == [call('file.torrent')]


@pytest.mark.skipif(sys.version_info < (3, 8), reason='No support for __aenter__ and __aexit__')
@pytest.mark.parametrize('download_path', (None, '', '/absolute/path', 'relative/path'))
@pytest.mark.parametrize('check_after_add', (True, False))
@pytest.mark.asyncio
async def test_add_torrent_calls_rpc_method(check_after_add, download_path, mocker):
    api = deluge.DelugeClientApi()

    mocks = Mock()
    mocks.attach_mock(
        mocker.patch.object(api, 'read_torrent_file', Mock(return_value=b'torrent metainfo')),
        'read_torrent_file',
    )
    mocks.attach_mock(
        mocker.patch.object(api._rpc, '__aenter__', AsyncMock()),
        'aenter',
    )
    mocks.attach_mock(
        # Return False to indicate exception must propagate
        mocker.patch.object(api._rpc, '__aexit__', AsyncMock(return_value=False)),
        'aexit',
    )
    mocks.attach_mock(
        mocker.patch.object(api._rpc, 'call', AsyncMock(return_value='D34DB33F')),
        'call',
    )
    mocker.patch.dict(api.config, check_after_add=check_after_add)

    torrent_path = 'path/to/file.torrent'
    exp_options = {
        'seed_mode': not check_after_add,
        'add_paused': False,
    }
    if download_path:
        exp_options['download_location'] = os.path.abspath(download_path)

    torrent_hash = await api.add_torrent(
        torrent_path=torrent_path,
        download_path=download_path,
    )
    assert torrent_hash == 'd34db33f'
    exp_mock_calls = [
        call.read_torrent_file(torrent_path),
        call.call(
            'core.add_torrent_file',
            filename='file.torrent',
            filedump=str(
                base64.b64encode(b'torrent metainfo'),
                encoding='ascii',
            ),
            options=exp_options,
        ),
    ]
    if check_after_add:
        exp_mock_calls.append(
            call.call('core.force_recheck', ['D34DB33F']),
        )
    assert mocks.mock_calls == exp_mock_calls

@pytest.mark.skipif(sys.version_info < (3, 8), reason='No support for __aenter__ and __aexit__')
@pytest.mark.parametrize(
    argnames='exception, exp_result',
    argvalues=(
        (aiobtclientrpc.ConnectionError('no connection'), errors.RequestError('no connection')),
        (aiobtclientrpc.AuthenticationError('authentication failed'), errors.RequestError('authentication failed')),
        (aiobtclientrpc.TimeoutError('timeout'), errors.RequestError('timeout')),
        (aiobtclientrpc.ValueError('invalid value'), errors.RequestError('invalid value')),
        (aiobtclientrpc.RPCError('wat'), errors.RequestError('wat')),
        (aiobtclientrpc.Error('Torrent already in session (F00fa99)'), 'f00fa99'),
    ),
    ids=lambda v: repr(v),
)
@pytest.mark.asyncio
async def test_add_torrent_catches_error_from_rpc_method_call(exception, exp_result, mocker):
    api = deluge.DelugeClientApi()

    mocker.patch.object(api, 'read_torrent_file', Mock(return_value=b'torrent metainfo')),
    mocker.patch.object(api._rpc, '__aenter__', AsyncMock()),
    # Return False to indicate exception must propagate
    mocker.patch.object(api._rpc, '__aexit__', AsyncMock(return_value=False)),
    mocker.patch.object(api._rpc, 'call', AsyncMock(side_effect=exception)),

    torrent_path = 'path/to/file.torrent'

    if isinstance(exp_result, BaseException):
        with pytest.raises(errors.RequestError, match=rf'^{re.escape(str(exception))}$'):
            await api.add_torrent(torrent_path=torrent_path)
    else:
        return_value = await api.add_torrent(torrent_path=torrent_path)
        assert return_value == exp_result

    assert api.read_torrent_file.call_args_list == [call(torrent_path)]
    assert api._rpc.call.call_args_list == [
        call(
            'core.add_torrent_file',
            filename='file.torrent',
            filedump=str(
                base64.b64encode(b'torrent metainfo'),
                encoding='ascii',
            ),
            options={'seed_mode': True, 'add_paused': False},
        ),
    ]
