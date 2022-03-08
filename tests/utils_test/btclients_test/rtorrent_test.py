import copy
import os
import re
import types
from unittest.mock import Mock, PropertyMock, call, patch

import aiobtclientrpc
import pytest

from upsies import errors
from upsies.utils.btclients import rtorrent


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_name():
    assert rtorrent.RtorrentClientApi.name == 'rtorrent'


def test_label():
    assert rtorrent.RtorrentClientApi.label == 'rTorrent'


def test_default_config():
    assert rtorrent.RtorrentClientApi.default_config == {
        'url': 'scgi://localhost:5000',
        'username': '',
        'password': '',
        'check_after_add': False,
    }


@pytest.mark.parametrize('username', (None, '', 'foo'))
@pytest.mark.parametrize('password', (None, '', 'bar'))
def test_rpc(username, password, mocker):
    RtorrentRPC_mock = mocker.patch('aiobtclientrpc.RtorrentRPC', Mock())
    api = rtorrent.RtorrentClientApi()
    mocker.patch.dict(api.config, username=username, password=password)
    rpc = api._rpc
    assert rpc is RtorrentRPC_mock.return_value
    assert RtorrentRPC_mock.call_args_list == [call(
        url=api.config['url'],
        username=api.config['username'] if username else None,
        password=api.config['password'] if password else None,
    )]
    assert rpc is api._rpc  # Singleton property


@pytest.mark.parametrize(
    argnames='download_path, exp_directory_set',
    argvalues=(
        (None, None),
        ('', None),
        ('/"absolute"/path', r'd.directory.set="/\"absolute\"/path"'),
        ('"relative"/path/', r'd.directory.set="{cwd}/\"relative\"/path"'),

    ),
)
@pytest.mark.asyncio
async def test_add_torrent(download_path, exp_directory_set, mocker):
    torrent_path = 'file.torrent'
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_get_torrent_data', return_value='torrent data')
    mocker.patch.object(client, 'read_torrent', return_value=Mock(infohash='d34db33f'))
    mocker.patch.object(client._rpc, 'call', AsyncMock())
    mocker.patch.object(client, '_get_load_command', AsyncMock())
    mocker.patch.object(client, '_wait_for_added_torrent', AsyncMock())

    exp_args = ['', client._get_torrent_data.return_value]
    if exp_directory_set:
        exp_args.append(exp_directory_set.format(cwd=os.getcwd()))

    return_value = await client.add_torrent(torrent_path, download_path)
    assert return_value == 'd34db33f'
    if download_path:
        assert client._get_torrent_data.call_args_list == [call(os.path.abspath(torrent_path),
                                                                os.path.abspath(download_path))]
    else:
        assert client._get_torrent_data.call_args_list == [call(os.path.abspath(torrent_path),
                                                                download_path)]
    assert client.read_torrent.call_args_list == [call(os.path.abspath(torrent_path))]
    assert client._get_load_command.call_args_list == [call()]
    assert client._rpc.call.call_args_list == [call(client._get_load_command.return_value, *exp_args)]
    assert client._wait_for_added_torrent.call_args_list == [call('d34db33f')]

@pytest.mark.asyncio
async def test_add_torrent_catches_torrent_error_from_getting_torrent_data(mocker):
    torrent_path = 'file.torrent'
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_get_torrent_data', side_effect=errors.TorrentError('huh'))
    mocker.patch.object(client, 'read_torrent', return_value=Mock(infohash='d34db33f'))
    mocker.patch.object(client._rpc, 'call', AsyncMock())
    mocker.patch.object(client, '_get_load_command', AsyncMock())
    mocker.patch.object(client, '_wait_for_added_torrent', AsyncMock())

    with pytest.raises(errors.RequestError, match=r'^huh$'):
        await client.add_torrent(torrent_path)

    assert client._get_torrent_data.call_args_list == [call(os.path.abspath(torrent_path), None)]
    assert client.read_torrent.call_args_list == []
    assert client._get_load_command.call_args_list == []
    assert client._rpc.call.call_args_list == []
    assert client._wait_for_added_torrent.call_args_list == []

@pytest.mark.asyncio
async def test_add_torrent_catches_torrent_error_from_reading_infohash(mocker):
    torrent_path = 'file.torrent'
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_get_torrent_data', return_value='torrent data')
    mocker.patch.object(client, 'read_torrent', side_effect=errors.TorrentError('huh'))
    mocker.patch.object(client._rpc, 'call', AsyncMock())
    mocker.patch.object(client, '_get_load_command', AsyncMock())
    mocker.patch.object(client, '_wait_for_added_torrent', AsyncMock())

    with pytest.raises(errors.RequestError, match=r'^huh$'):
        await client.add_torrent(torrent_path)

    assert client._get_torrent_data.call_args_list == [call(os.path.abspath(torrent_path), None)]
    assert client.read_torrent.call_args_list == [call(os.path.abspath(torrent_path))]
    assert client._get_load_command.call_args_list == []
    assert client._rpc.call.call_args_list == []
    assert client._wait_for_added_torrent.call_args_list == []

@pytest.mark.asyncio
async def test_add_torrent_catches_request_error_from_getting_load_command(mocker):
    torrent_path = 'file.torrent'
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_get_torrent_data', return_value='torrent data')
    mocker.patch.object(client, 'read_torrent', return_value=Mock(infohash='d34db33f'))
    mocker.patch.object(client._rpc, 'call', AsyncMock())
    mocker.patch.object(client, '_get_load_command', AsyncMock(side_effect=aiobtclientrpc.Error('wat')))
    mocker.patch.object(client, '_wait_for_added_torrent', AsyncMock())

    with pytest.raises(errors.RequestError, match=r'^wat$'):
        await client.add_torrent(torrent_path)

    assert client._get_torrent_data.call_args_list == [call(os.path.abspath(torrent_path), None)]
    assert client.read_torrent.call_args_list == [call(os.path.abspath(torrent_path))]
    assert client._get_load_command.call_args_list == [call()]
    assert client._rpc.call.call_args_list == []
    assert client._wait_for_added_torrent.call_args_list == []

@pytest.mark.asyncio
async def test_add_torrent_catches_request_error_from_calling_load_command(mocker):
    torrent_path = 'file.torrent'
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_get_torrent_data', return_value='torrent data')
    mocker.patch.object(client, 'read_torrent', return_value=Mock(infohash='d34db33f'))
    mocker.patch.object(client._rpc, 'call', AsyncMock(side_effect=aiobtclientrpc.Error('wat')))
    mocker.patch.object(client, '_get_load_command', AsyncMock())
    mocker.patch.object(client, '_wait_for_added_torrent', AsyncMock())

    with pytest.raises(errors.RequestError, match=r'^wat$'):
        await client.add_torrent(torrent_path)

    assert client._get_torrent_data.call_args_list == [call(os.path.abspath(torrent_path), None)]
    assert client.read_torrent.call_args_list == [call(os.path.abspath(torrent_path))]
    assert client._get_load_command.call_args_list == [call()]
    assert client._rpc.call.call_args_list == [call(client._get_load_command.return_value, '', 'torrent data')]
    assert client._wait_for_added_torrent.call_args_list == []

@pytest.mark.asyncio
async def test_add_torrent_catches_request_error_from_waiting_for_torrent(mocker):
    torrent_path = 'file.torrent'
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_get_torrent_data', return_value='torrent data')
    mocker.patch.object(client, 'read_torrent', return_value=Mock(infohash='d34db33f'))
    mocker.patch.object(client._rpc, 'call', AsyncMock())
    mocker.patch.object(client, '_get_load_command', AsyncMock())
    mocker.patch.object(client, '_wait_for_added_torrent', AsyncMock(side_effect=aiobtclientrpc.Error('wat')))

    with pytest.raises(errors.RequestError, match=r'^wat$'):
        await client.add_torrent(torrent_path)

    assert client._get_torrent_data.call_args_list == [call(os.path.abspath(torrent_path), None)]
    assert client.read_torrent.call_args_list == [call(os.path.abspath(torrent_path))]
    assert client._get_load_command.call_args_list == [call()]
    assert client._rpc.call.call_args_list == [call(client._get_load_command.return_value, '', 'torrent data')]
    assert client._wait_for_added_torrent.call_args_list == [call('d34db33f')]


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
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_add_torrent_timeout', 0.5)
    mocker.patch.object(client, '_add_torrent_check_delay', 0.1)
    mocker.patch.object(client, '_get_torrent_hashes', AsyncMock(side_effect=torrent_hashes))

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await client._wait_for_added_torrent(infohash)
    else:
        return_value = await client._wait_for_added_torrent(infohash)
        assert return_value is None


@pytest.mark.parametrize(
    argnames='methods, exp_command, exp_exception',
    argvalues=(
        (['load.raw_start'], 'load.raw_start', None),
        (['load.raw_start', 'load.raw_start_verbose'], 'load.raw_start_verbose', None),
        (['load.raw_start_verbose', 'load.raw_start'], 'load.raw_start_verbose', None),
        ([], None, RuntimeError('Failed to find load command')),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_get_load_command(methods, exp_command, exp_exception, mocker):
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client._rpc, 'call', AsyncMock(return_value=methods))

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await client._get_load_command()
    else:
        return_value = await client._get_load_command()
        assert return_value == exp_command


@pytest.mark.parametrize('download_path', (None, '', 'path/to/downloads/'))
@pytest.mark.parametrize('config', ({'check_after_add': True}, {'check_after_add': False}), ids=lambda v: str(v))
@pytest.mark.parametrize('exception', (None, errors.TorrentError('no')), ids=lambda v: str(v))
def test_get_torrent_data(exception, config, download_path, mocker):
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(type(client), 'config', PropertyMock(return_value=config))
    if exception:
        mocker.patch.object(client, '_get_torrent_data_with_resume_fields',
                            side_effect=exception)
    else:
        mocker.patch.object(client, '_get_torrent_data_with_resume_fields',
                            return_value=Mock(dump=Mock(return_value='torrent with resume fields')))
    mocker.patch.object(client, 'read_torrent',
                        return_value=Mock(dump=Mock(return_value='torrent without resume fields')))

    torrent_path = 'path/to/file.torrent'
    torrent_data = client._get_torrent_data(torrent_path, download_path=download_path)

    if download_path and not config['check_after_add']:
        assert client._get_torrent_data_with_resume_fields.call_args_list == [
            call(torrent_path, download_path)
        ]
        if exception:
            assert client.read_torrent.call_args_list == [call(torrent_path)]
            assert torrent_data == 'torrent without resume fields'
        else:
            assert client.read_torrent.call_args_list == []
            assert torrent_data == 'torrent with resume fields'
    else:
        assert client.read_torrent.call_args_list == [call(torrent_path)]
        assert torrent_data == 'torrent without resume fields'


def test_get_torrent_data_with_resume_fields(mocker):
    mocks = Mock()
    client = rtorrent.RtorrentClientApi()
    metainfo = {
        'info': {
            'pieces': b'\x00' * 100,
        },
        'comment': 'This should be preserved.',
    }
    file_data = (
        {'path': 'this/file.txt', 'mtime': 123, 'piece_indexes': [0, 1, 2]},
        {'path': 'that/file.jpg', 'mtime': 456, 'piece_indexes': [2, 3, 4, 5, 6]},
        {'path': 'another/file/path.mp4', 'mtime': 789, 'piece_indexes': [7, 8]},
    )

    mocks.attach_mock(
        mocker.patch.object(client, 'read_torrent', return_value=types.SimpleNamespace(
            metainfo=metainfo,
            files=[fd['path'] for fd in file_data],
        )),
        'read_torrent',
    )
    mocks.attach_mock(
        mocker.patch(
            'upsies.utils.torrent.TorrentFileStream',
        ),
        'TorrentFileStream',
    )
    mocks.TorrentFileStream.return_value.__enter__.return_value.get_piece_indexes_for_file.side_effect = [
        fd['piece_indexes'] for fd in file_data]
    mocks.attach_mock(
        mocker.patch.object(client, '_get_mtime', side_effect=[
            fd['mtime'] for fd in file_data
        ]),
        '_get_mtime',
    )

    torrent = client._get_torrent_data_with_resume_fields(
        'path/to/file.torrent',
        'path/to/content',
    )

    exp_metainfo = copy.deepcopy(metainfo)
    exp_metainfo['libtorrent_resume'] = {
        'files': [
            {'mtime': fd['mtime'], 'completed': len(fd['piece_indexes']), 'priority': 0}
            for fd in file_data
        ],
        'bitfield': len(metainfo['info']['pieces']) // 20,
    }
    assert torrent.metainfo == exp_metainfo

    exp_mock_calls = [
        call.read_torrent('path/to/file.torrent'),
        call.TorrentFileStream(mocks.read_torrent.return_value, 'path/to/content'),
        call.TorrentFileStream().__enter__(),
    ]
    for fd in file_data:
        exp_mock_calls.extend((
            call._get_mtime(os.path.join('path/to/content', fd['path'])),
            call.TorrentFileStream().__enter__().get_piece_indexes_for_file(fd['path']),
        ))
    exp_mock_calls.append(call.TorrentFileStream().__exit__(None, None, None))
    assert mocks.mock_calls == exp_mock_calls


# NOTE: We must use patch() for mocking os.stat() because mocking with mocker
#       seems to interfere with pytest's internals.

def test_get_mtime_returns_int():
    client = rtorrent.RtorrentClientApi()
    with patch('os.stat') as stat_mock:
        stat_mock.return_value = Mock(st_mtime=123.123)
        mtime = client._get_mtime('some/path')
        assert mtime == 123
        assert stat_mock.call_args_list == [call('some/path')]

@pytest.mark.parametrize('exception', (OSError('nope'), OSError(123, 'nope')))
def test_get_mtime_catches_OSError(exception):
    client = rtorrent.RtorrentClientApi()
    with patch('os.stat', side_effect=exception) as stat_mock:
        with pytest.raises(errors.TorrentError, match=r'^nope$'):
            client._get_mtime('some/path')
        assert stat_mock.call_args_list == [call('some/path')]


@pytest.mark.asyncio
async def test_get_torrent_hashes(mocker):
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client._rpc, 'call', AsyncMock(return_value=['D34D', 'B33F']))
    hashes = await client._get_torrent_hashes()
    assert hashes == ('d34d', 'b33f')
    assert client._rpc.call.call_args_list == [call('download_list')]
