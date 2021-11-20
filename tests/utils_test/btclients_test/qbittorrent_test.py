import os
import re
from unittest.mock import Mock, call

import pytest
import torf

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


def test_default_config():
    assert qbittorrent.QbittorrentClientApi.default_config == {
        'url': 'http://localhost:8080',
        'username': '',
        'password': '',
    }


@pytest.mark.parametrize(
    argnames='config, exp_headers',
    argvalues=(
        ({'url': 'http://localhost'}, {'Referer': 'http://localhost'}),
        ({'url': 'http://localhost:8080'}, {'Referer': 'http://localhost:8080'}),
        ({'url': 'http://localhost:8080/api'}, {'Referer': 'http://localhost:8080'}),
    ),
    ids=lambda v: str(v),
)
def test_attributes(config, exp_headers):
    client = qbittorrent.QbittorrentClientApi(config=config)
    assert client._headers == exp_headers


@pytest.mark.parametrize(
    argnames='config_url, path, exp_request_url',
    argvalues=(
        ('http://localhost:8080', '/foo', 'http://localhost:8080/api/v2/foo'),
        ('http://localhost:8080', 'foo', 'http://localhost:8080/api/v2/foo'),
        ('http://localhost:8080/', '/foo', 'http://localhost:8080/api/v2/foo'),
        ('http://localhost:8080/', 'foo', 'http://localhost:8080/api/v2/foo'),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_request(config_url, path, exp_request_url, mocker):
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    client = qbittorrent.QbittorrentClientApi(config={'url': config_url})
    data = 'mock data'
    files = 'mock files'
    await client._request(path, data=data, files=files)
    assert post_mock.call_args_list == [call(
        url=exp_request_url,
        headers=client._headers,
        data=data,
        files=files
    )]


@pytest.mark.parametrize(
    argnames='response, exception, exp_exception',
    argvalues=(
        ('Ok.', None, None),
        ('Fails.', None, errors.RequestError('Authentication failed')),
        (None, errors.RequestError('qBittorrent: Bad request'), errors.RequestError('qBittorrent: Bad request')),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_login(response, exception, exp_exception, mocker):
    client = qbittorrent.QbittorrentClientApi(config={
        'username': 'me',
        'password': 'moo',
        'foo': 'bar',
    })
    if exception:
        mocker.patch.object(client, '_request', AsyncMock(side_effect=exception))
    else:
        mocker.patch.object(client, '_request', AsyncMock(return_value=response))

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await client._login()
    else:
        await client._login()

    assert client._request.call_args_list == [call(
        path='auth/login',
        data={'username': 'me', 'password': 'moo'},
    )]


@pytest.mark.asyncio
async def test_logout(mocker):
    client = qbittorrent.QbittorrentClientApi()
    mocker.patch.object(client, '_request', AsyncMock())
    await client._logout()
    assert client._request.call_args_list == [call(path='auth/logout')]


@pytest.mark.asyncio
async def test_session(mocker):
    client = qbittorrent.QbittorrentClientApi()
    mocker.patch.object(client, '_login', AsyncMock())
    mocker.patch.object(client, '_logout', AsyncMock())
    assert client._login.call_args_list == []
    assert client._logout.call_args_list == []
    async with client._session():
        assert client._login.call_args_list == [call()]
        assert client._logout.call_args_list == []
    assert client._login.call_args_list == [call()]
    assert client._logout.call_args_list == [call()]


@pytest.mark.parametrize(
    argnames='login_exception, logout_exception, exp_exception',
    argvalues=(
        (None, None, None),
        (errors.RequestError('Login failed'), None, errors.RequestError('Login failed')),
        (None, errors.RequestError('Logout failed'), errors.RequestError('Logout failed')),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_add_torrent_handles_RequestError_from_authentication(login_exception, logout_exception, exp_exception, mocker):
    client = qbittorrent.QbittorrentClientApi()
    mocker.patch.object(client, '_login', AsyncMock(side_effect=login_exception))
    mocker.patch.object(client, '_logout', AsyncMock(side_effect=logout_exception))
    mocker.patch.object(client, '_request', AsyncMock(return_value='Ok.'))
    mocker.patch.object(client, '_get_torrent_hash', Mock(return_value='D34DB33F'))

    coro = client.add_torrent('path/to/file.torrent')
    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await coro
    else:
        assert await coro == 'D34DB33F'

    assert client._login.call_args_list == [call()]
    if not login_exception:
        assert client._logout.call_args_list == [call()]
    else:
        assert client._logout.call_args_list == []


@pytest.mark.parametrize(
    argnames='response, exception, exp_exception',
    argvalues=(
        (None, errors.RequestError('qBittorrent: No'), errors.RequestError('qBittorrent: No')),
        ('Fails.', None, errors.RequestError('Unknown error')),
        ('Ok.', None, None),
    ),
    ids=lambda v: repr(v),
)
@pytest.mark.parametrize('download_path', (None, '', 'path/to/downloads'))
@pytest.mark.asyncio
async def test_add_torrent_handles_RequestError_from_adding(download_path, response, exception, exp_exception, mocker):
    torrent_path = 'path/to/file.torrent'
    torrent_hash = 'D34DB33F'
    client = qbittorrent.QbittorrentClientApi()

    mocker.patch.object(client, '_login', AsyncMock())
    mocker.patch.object(client, '_logout', AsyncMock())

    if exception:
        mocker.patch.object(client, '_request', AsyncMock(side_effect=exception))
    else:
        mocker.patch.object(client, '_request', AsyncMock(return_value=response))
    mocker.patch.object(client, '_get_torrent_hash', Mock(return_value=torrent_hash))

    coro = client.add_torrent(torrent_path, download_path=download_path)
    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await coro
        assert client._get_torrent_hash.call_args_list == []
    else:
        assert await coro == torrent_hash
        assert client._get_torrent_hash.call_args_list == [call(torrent_path)]

    exp_files = {
        'torrents': {
            'file': 'path/to/file.torrent',
            'mimetype': 'application/x-bittorrent',
        },
    }
    if download_path:
        exp_data = {'savepath': os.path.abspath(download_path)}
    else:
        exp_data = {}
    assert client._request.call_args_list == [call('torrents/add', files=exp_files, data=exp_data)]


@pytest.mark.parametrize(
    argnames='exception, exp_exception',
    argvalues=(
        (None, None),
        (torf.TorfError('Permission denied'), errors.RequestError('Permission denied')),
    ),
    ids=lambda v: repr(v),
)
@pytest.mark.asyncio
async def test_get_torrent_hash(exception, exp_exception, mocker):
    torrent_path = 'path/to/file.torrent'
    torrent_hash = 'D34DB33F'
    client = qbittorrent.QbittorrentClientApi()
    read_mock = mocker.patch('torf.Torrent.read',
                             side_effect=exception,
                             return_value=Mock(infohash=torrent_hash))
    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            client._get_torrent_hash(torrent_path)
    else:
        assert client._get_torrent_hash(torrent_path) == torrent_hash
    assert read_mock.call_args_list == [call(torrent_path)]
