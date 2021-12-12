import copy
import http
import os
import types
import urllib
import xmlrpc
from unittest.mock import Mock, PropertyMock, call, patch

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


def test_proxy_with_empty_url(mocker):
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(type(client), 'config', PropertyMock(return_value={'url': ''}))
    with pytest.raises(errors.RequestError, match=r'^No URL provided$'):
        client._proxy

@pytest.mark.parametrize(
    argnames='url, exp_uri, exp_transport, exp_socket_path',
    argvalues=(
        ('HTTP://localhost:5000/', 'http://localhost:5000/', None, None),
        ('scgi://localhost:5000/', 'http://localhost:5000/', 'ScgiTransport', None),
        ('scgi:///path/to/socket', 'http://1', 'ScgiTransport', '/path/to/socket'),
        ('SCGI://path/to/socket', 'http://1', 'ScgiTransport', 'path/to/socket'),
    ),
    ids=lambda v: str(v),
)
def test_proxy_returns_ServerProxy_object(url, exp_uri, exp_transport, exp_socket_path, mocker):
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(type(client), 'config', PropertyMock(return_value={'url': url}))
    ScgiTransport_mock = mocker.patch('upsies.utils.btclients.rtorrent._scgi.ScgiTransport')
    ServerProxy_mock = mocker.patch('xmlrpc.client.ServerProxy')
    proxy = client._proxy

    if exp_transport == 'ScgiTransport':
        if exp_socket_path:
            assert ScgiTransport_mock.call_args_list == [call(socket_path=exp_socket_path)]
            exp_serverproxy_kwargs = {
                'uri': 'http://1',
                'transport': ScgiTransport_mock.return_value,
            }
        else:
            assert ScgiTransport_mock.call_args_list == [call()]
            exp_serverproxy_kwargs = {
                'uri': 'http://' + urllib.parse.urlsplit(url).netloc,
                'transport': ScgiTransport_mock.return_value,
            }
    else:
        assert ScgiTransport_mock.call_args_list == []
        exp_serverproxy_kwargs = {
            'uri': url,
        }

    assert ServerProxy_mock.call_args_list == [call(**exp_serverproxy_kwargs)]
    # Test if client._proxy is singleton
    assert client._proxy is proxy


def test_request_succeeds():
    client = rtorrent.RtorrentClientApi()
    client._proxy = Mock()
    return_value = client._request('foo.bar.baz', 'a', 'b', 'c')
    assert client._proxy.foo.bar.baz.call_args_list == [call('a', 'b', 'c')]
    assert return_value == client._proxy.foo.bar.baz.return_value

@pytest.mark.parametrize(
    argnames='exception',
    argvalues=(
        http.client.HTTPException('nope'),
        xmlrpc.client.ProtocolError('host:8080', 123, 'nope', {'foo': 'bar'}),
        OSError('nope'),
        OSError(123, 'nope'),
    ),
    ids=lambda v: str(v),
)
def test_request_fails(exception):
    client = rtorrent.RtorrentClientApi()
    client._proxy = Mock()
    client._proxy.foo.bar.baz.side_effect = exception
    with pytest.raises(errors.RequestError, match=r'^nope$'):
        client._request('foo.bar.baz', 'a', 'b', 'c')
    assert client._proxy.foo.bar.baz.call_args_list == [call('a', 'b', 'c')]


def test_get_torrent_hashes(mocker):
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_request', return_value=['D34D', 'B33F'])
    hashes = client._get_torrent_hashes()
    assert hashes == ('d34d', 'b33f')
    assert client._request.call_args_list == [call('download_list')]


@pytest.mark.parametrize(
    argnames='download_path, exp_directory_set',
    argvalues=(
        (None, None),
        ('', None),
        ('path/to/downloads/', 'd.directory.set="{escaped_absolute_download_path}"'),
        ('path/to/"down"loads/', r'd.directory.set="{escaped_absolute_download_path}"'),
    ),
)
@pytest.mark.asyncio
async def test_add_torrent_succeeds(download_path, exp_directory_set, mocker):
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_get_load_command', AsyncMock(return_value='load.raw_start_verbose'))
    mocker.patch.object(client, '_get_torrent_data', return_value='mock torrent data')
    mocker.patch.object(client, 'read_torrent', return_value=Mock(infohash='D34DB33F'))
    mocker.patch.object(client, '_request')
    mocker.patch.object(client, '_get_torrent_hashes', side_effect=[
        ['C0FF33', 'B4B3'],
        ['C0FF33', 'B4B3'],
        ['C0FF33', 'B4B3', 'D34DB33F'],
    ])
    mocker.patch.object(type(client), 'add_torrent_check_delay', 0)

    torrent_path = 'path/to/file.torrent'
    torrent_path_abs = os.path.abspath(torrent_path)
    download_path_abs = os.path.abspath(download_path) if download_path else download_path
    await client.add_torrent(torrent_path, download_path=download_path)

    assert client._get_torrent_data.call_args_list == [call(torrent_path_abs, download_path_abs)]
    exp_request_args = ['', 'mock torrent data']
    if exp_directory_set:
        exp_request_args.append(exp_directory_set.format(
            escaped_absolute_download_path=download_path_abs.replace('"', r'\"'),
        ))
    assert client._request.call_args_list == [call('load.raw_start_verbose', *exp_request_args)]
    assert client.read_torrent.call_args_list == [call(torrent_path_abs)]
    assert client._get_torrent_hashes.call_args_list == [call(), call(), call()]

@pytest.mark.asyncio
async def test_add_torrent_fails_to_get_torrent_data(mocker):
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_get_torrent_data', side_effect=errors.TorrentError('no'))
    mocker.patch.object(client, 'read_torrent')
    mocker.patch.object(client, '_request')
    mocker.patch.object(client, '_get_torrent_hashes', return_value=[])
    mocker.patch.object(type(client), 'add_torrent_check_delay', 0)

    with pytest.raises(errors.RequestError, match=r'^no$'):
        await client.add_torrent('/path/to/file.torrent', download_path='/path/to/downloads/')

    assert client._get_torrent_data.call_args_list == [call('/path/to/file.torrent', '/path/to/downloads')]
    assert client._request.call_args_list == []
    assert client.read_torrent.call_args_list == []
    assert client._get_torrent_hashes.call_args_list == []

@pytest.mark.asyncio
async def test_add_torrent_fails_to_read_torrent(mocker):
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_get_load_command', AsyncMock(return_value='load.raw_start_verbose'))
    mocker.patch.object(client, '_get_torrent_data', return_value='mock torrent data')
    mocker.patch.object(client, 'read_torrent', side_effect=errors.TorrentError('no'))
    mocker.patch.object(client, '_request')
    mocker.patch.object(client, '_get_torrent_hashes', return_value=[])
    mocker.patch.object(type(client), 'add_torrent_check_delay', 0)

    with pytest.raises(errors.RequestError, match=r'^no$'):
        await client.add_torrent('/path/to/file.torrent', download_path='/path/to/downloads/')

    assert client._get_torrent_data.call_args_list == [call('/path/to/file.torrent', '/path/to/downloads')]
    assert client._request.call_args_list == [call(
        'load.raw_start_verbose',
        '', 'mock torrent data', 'd.directory.set="/path/to/downloads"',
    )]
    assert client.read_torrent.call_args_list == [call('/path/to/file.torrent')]
    assert client._get_torrent_hashes.call_args_list == []

@pytest.mark.asyncio
async def test_add_torrent_fails_after_timeout(mocker):
    client = rtorrent.RtorrentClientApi()
    mocker.patch.object(client, '_get_load_command', AsyncMock(return_value='load.raw_start_verbose'))
    mocker.patch.object(client, '_get_torrent_data', return_value='mock torrent data')
    mocker.patch.object(client, 'read_torrent', return_value=Mock(infohash='D34DB33F'))
    mocker.patch.object(client, '_request')
    mocker.patch.object(type(client), 'add_torrent_check_delay', 0.01)
    mocker.patch.object(type(client), 'add_torrent_timeout', 0.03)
    exp_attempts = int(client.add_torrent_timeout / client.add_torrent_check_delay)
    mocker.patch.object(client, '_get_torrent_hashes', side_effect=(
        ([['C0FF33', 'B4B3']] * exp_attempts)
        + [['C0FF33', 'B4B3', 'D34DB33F']]
    ))

    with pytest.raises(errors.RequestError, match=r'^Unknown error$'):
        await client.add_torrent('/path/to/file.torrent', download_path='/path/to/downloads/')

    assert client._get_torrent_data.call_args_list == [call('/path/to/file.torrent', '/path/to/downloads')]
    assert client._request.call_args_list == [call(
        'load.raw_start_verbose',
        '', 'mock torrent data', 'd.directory.set="/path/to/downloads"',
    )]
    assert client.read_torrent.call_args_list == [call('/path/to/file.torrent')]
    assert client._get_torrent_hashes.call_args_list == [call()] * exp_attempts


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
