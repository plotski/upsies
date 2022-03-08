import os
import re
import sys
from unittest.mock import Mock, PropertyMock, call

import aiobtclientrpc
import pytest

from upsies import errors
from upsies.utils.btclients import qbittorrent


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    async def __aenter__(self, *args, **kwargs):
        return self.aenter

    async def __aexit__(self, *args, **kwargs):
        pass


def test_name():
    assert qbittorrent.QbittorrentClientApi.name == 'qbittorrent'


def test_label():
    assert qbittorrent.QbittorrentClientApi.label == 'qBittorrent'


def test_default_config():
    assert qbittorrent.QbittorrentClientApi.default_config == {
        'url': 'http://localhost:8080',
        'username': '',
        'password': '',
        'check_after_add': False,
    }

@pytest.mark.parametrize('username', (None, '', 'foo'))
@pytest.mark.parametrize('password', (None, '', 'bar'))
def test_rpc(username, password, mocker):
    QbittorrentRPC_mock = mocker.patch('aiobtclientrpc.QbittorrentRPC', Mock())
    api = qbittorrent.QbittorrentClientApi()
    mocker.patch.dict(api.config, username=username, password=password)
    rpc = api._rpc
    assert rpc is QbittorrentRPC_mock.return_value
    assert QbittorrentRPC_mock.call_args_list == [call(
        url=api.config['url'],
        username=api.config['username'] if username else None,
        password=api.config['password'] if password else None,
    )]
    assert rpc is api._rpc  # Singleton property


@pytest.mark.asyncio
async def test_add_torrent_fails_to_read_torrent_file(mocker):
    api = qbittorrent.QbittorrentClientApi()

    mocker.patch.object(api, 'read_torrent_file', Mock(
        side_effect=errors.TorrentError('Unable to read torrent file'),
    ))
    mocker.patch.object(api, 'read_torrent', Mock())
    mocker.patch.object(type(api), '_rpc', PropertyMock(
        return_value="This is not an async context manager, but I don't care.",
    ))

    with pytest.raises(errors.RequestError, match=r'^Unable to read torrent file$'):
        await api.add_torrent(torrent_path='file.torrent')

    assert api.read_torrent_file.call_args_list == [call('file.torrent')]


@pytest.mark.asyncio
async def test_add_torrent_fails_to_read_torrent(mocker):
    api = qbittorrent.QbittorrentClientApi()

    mocker.patch.object(api, 'read_torrent_file', Mock())
    mocker.patch.object(api, 'read_torrent', Mock(
        side_effect=errors.TorrentError('Unable to read torrent'),
    ))
    mocker.patch.object(type(api), '_rpc', PropertyMock(
        return_value="This is not an async context manager, but that's OK.",
    ))

    with pytest.raises(errors.RequestError, match=r'^Unable to read torrent$'):
        await api.add_torrent(torrent_path='file.torrent')

    assert api.read_torrent_file.call_args_list == [call('file.torrent')]


@pytest.mark.skipif(sys.version_info < (3, 8), reason='No support for __aenter__ and __aexit__')
@pytest.mark.parametrize('download_path', (None, '', '/absolute/path', 'relative/path'))
@pytest.mark.parametrize('check_after_add', (True, False))
@pytest.mark.asyncio
async def test_add_torrent_calls_rpc_method(check_after_add, download_path, mocker):
    api = qbittorrent.QbittorrentClientApi()

    mocks = Mock()
    mocks.attach_mock(
        mocker.patch.object(api, 'read_torrent_file', Mock(return_value=b'torrent metainfo')),
        'read_torrent_file',
    )
    mocks.attach_mock(
        mocker.patch.object(api, 'read_torrent', return_value=Mock(infohash='torrent infohash')),
        'read_torrent',
    )
    mocks.attach_mock(
        mocker.patch.object(api, '_wait_for_added_torrent', AsyncMock()),
        '_wait_for_added_torrent',
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
        mocker.patch.object(api._rpc, 'call', AsyncMock()),
        'call',
    )
    mocker.patch.dict(api.config, check_after_add=check_after_add)

    torrent_path = 'path/to/file.torrent'
    exp_files = [
        ('filename', (
            os.path.basename(torrent_path),  # File name
            b'torrent metainfo',             # File content
            'application/x-bittorrent',      # MIME type
        )),
    ]
    exp_options = {
        'skip_checking': str(not check_after_add).lower(),
    }
    if download_path:
        exp_options['savepath'] = os.path.abspath(download_path)

    torrent_hash = await api.add_torrent(
        torrent_path=torrent_path,
        download_path=download_path,
    )
    assert torrent_hash == 'torrent infohash'
    assert mocks.mock_calls == [
        call.read_torrent_file(torrent_path),
        call.read_torrent(torrent_path),
        call.call('torrents/add', files=exp_files, **exp_options),
        call._wait_for_added_torrent('torrent infohash'),
    ]


@pytest.mark.skipif(sys.version_info < (3, 8), reason='No support for __aenter__ and __aexit__')
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
    api = qbittorrent.QbittorrentClientApi()

    mocker.patch.object(api, 'read_torrent_file', Mock(return_value=b'torrent metainfo')),
    mocker.patch.object(api, 'read_torrent', return_value=Mock(infohash='torrent infohash')),
    mocker.patch.object(api, '_wait_for_added_torrent', AsyncMock()),
    mocker.patch.object(api._rpc, '__aenter__', AsyncMock()),
    # Return False to indicate exception must propagate
    mocker.patch.object(api._rpc, '__aexit__', AsyncMock(return_value=False)),
    mocker.patch.object(api._rpc, 'call', AsyncMock(side_effect=exception)),

    torrent_path = 'path/to/file.torrent'
    exp_files = [
        ('filename', (
            os.path.basename(torrent_path),  # File name
            b'torrent metainfo',             # File content
            'application/x-bittorrent',      # MIME type
        )),
    ]

    with pytest.raises(errors.RequestError, match=rf'^{re.escape(str(exception))}$'):
        await api.add_torrent(torrent_path=torrent_path)

    assert api.read_torrent_file.call_args_list == [call(torrent_path)]
    assert api.read_torrent.call_args_list == [call(torrent_path)]
    assert api._rpc.call.call_args_list == [call('torrents/add', files=exp_files, skip_checking='true')]
    assert api._wait_for_added_torrent.call_args_list == []


@pytest.mark.skipif(sys.version_info < (3, 8), reason='No support for __aenter__ and __aexit__')
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
async def test_add_torrent_catches_error_from_wait_for_added_torrent(exception, mocker):
    api = qbittorrent.QbittorrentClientApi()

    mocker.patch.object(api, 'read_torrent_file', Mock(return_value=b'torrent metainfo')),
    mocker.patch.object(api, 'read_torrent', return_value=Mock(infohash='torrent infohash')),
    mocker.patch.object(api, '_wait_for_added_torrent', AsyncMock(side_effect=exception)),
    mocker.patch.object(api._rpc, '__aenter__', AsyncMock()),
    # Return False to indicate exception must propagate
    mocker.patch.object(api._rpc, '__aexit__', AsyncMock(return_value=False)),
    mocker.patch.object(api._rpc, 'call', AsyncMock()),

    torrent_path = 'path/to/file.torrent'
    exp_files = [
        ('filename', (
            os.path.basename(torrent_path),  # File name
            b'torrent metainfo',             # File content
            'application/x-bittorrent',      # MIME type
        )),
    ]

    with pytest.raises(errors.RequestError, match=rf'^{re.escape(str(exception))}$'):
        await api.add_torrent(torrent_path=torrent_path)

    assert api.read_torrent_file.call_args_list == [call(torrent_path)]
    assert api.read_torrent.call_args_list == [call(torrent_path)]
    assert api._rpc.call.call_args_list == [call('torrents/add', files=exp_files, skip_checking='true')]
    assert api._wait_for_added_torrent.call_args_list == [call('torrent infohash')]


@pytest.mark.parametrize(
    argnames='infohash, torrent_hashes, exp_exception',
    argvalues=(
        (
            'c0ff33',
            (['d34db33f'], ['d34db33f'], ['d34db33f'], ['d34db33f'], ['d34db33f']),
            errors.RequestError('Unknown error'),
        ),
        (
            'c0ff33',
            (['d34db33f'], ['d34db33f'], ['d34db33f', 'c0ff33']),
            None,
        ),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_wait_for_added_torrent(infohash, torrent_hashes, exp_exception, mocker):
    api = qbittorrent.QbittorrentClientApi()
    mocker.patch.object(api, '_add_torrent_timeout', 0.5)
    mocker.patch.object(api, '_add_torrent_check_delay', 0.1)
    mocker.patch.object(api, '_get_torrent_hashes', AsyncMock(side_effect=torrent_hashes))

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await api._wait_for_added_torrent(infohash)
    else:
        return_value = await api._wait_for_added_torrent(infohash)
        assert return_value is None


@pytest.mark.asyncio
async def test_get_torrent_hashes(mocker):
    api = qbittorrent.QbittorrentClientApi()
    mocker.patch.object(api._rpc, 'call', AsyncMock(return_value=[
        {'hash': 'D34D'},
        {'hash': 'B33F'},
    ]))
    hashes = await api._get_torrent_hashes('foo', 'bar', 'baz')
    assert hashes == ('d34d', 'b33f')
    assert api._rpc.call.call_args_list == [
        call('torrents/info', hashes=('foo', 'bar', 'baz')),
    ]
