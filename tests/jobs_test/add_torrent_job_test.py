from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.jobs.torrent import AddTorrentJob
from upsies.utils import btclients


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def client():
    class MockClient(btclients.ClientApiBase):
        name = 'mocksy'
        label = 'Mocksy'
        default_config = {}
        add_torrent = AsyncMock()

        def __repr__(self):
            return '<MockClient instance>'

    return MockClient()

@pytest.fixture
async def make_AddTorrentJob(tmp_path, client):
    def make_AddTorrentJob(download_path=tmp_path, torrents=()):
        return AddTorrentJob(
            home_directory=tmp_path,
            cache_directory=tmp_path,
            ignore_cache=False,
            client=client,
            enqueue=torrents,
            download_path=download_path,
        )
    return make_AddTorrentJob


def test_cache_id(make_AddTorrentJob):
    job = make_AddTorrentJob()
    assert job.cache_id is None


@pytest.mark.asyncio
async def test_handle_input_call_order(make_AddTorrentJob):
    job = make_AddTorrentJob()
    mocks = Mock()
    job.signal.register('adding', mocks.adding)
    job.signal.register('added', mocks.added)
    mocks.add_torrent = AsyncMock(return_value=123)
    job._client.add_torrent = mocks.add_torrent
    await job.handle_input('foo.torrent')
    assert mocks.mock_calls == [
        call.adding('foo.torrent'),
        call.add_torrent(torrent_path='foo.torrent', download_path=job._download_path),
        call.added(123),
    ]

@pytest.mark.asyncio
async def test_handle_input_complains_about_large_torrent_file(make_AddTorrentJob, tmp_path):
    torrent_file = tmp_path / 'foo.torrent'
    with open(torrent_file, 'wb') as f:
        f.truncate(AddTorrentJob.MAX_TORRENT_SIZE + 1)  # Sparse file

    job = make_AddTorrentJob()
    await job.handle_input(torrent_file)
    assert job.errors == (f'{torrent_file}: File is too large',)
    assert job.output == ()

@pytest.mark.asyncio
async def test_handle_input_catches_RequestError(make_AddTorrentJob):
    job = make_AddTorrentJob()
    job._client.add_torrent.side_effect = errors.RequestError('No such file or whatever')
    await job.handle_input('foo.torrent')
    assert job.errors == (
        'Failed to add foo.torrent to mocksy: No such file or whatever',
    )
    assert job.output == ()

@pytest.mark.asyncio
async def test_handle_input_sends_torrent_hash(make_AddTorrentJob):
    job = make_AddTorrentJob()
    job._client.add_torrent.return_value = '12345'
    await job.handle_input('foo.torrent')
    assert job.output == ('12345',)
    assert job.errors == ()

@pytest.mark.parametrize('torrent_hash', (None, ''))
@pytest.mark.asyncio
async def test_handle_input_does_not_send_falsy_torrent_hash(torrent_hash, make_AddTorrentJob):
    job = make_AddTorrentJob()
    job._client.add_torrent.return_value = torrent_hash
    await job.handle_input('foo.torrent')
    assert job.output == ()
    assert job.errors == ()

@pytest.mark.asyncio
async def test_handle_input_sets_info_property_on_success(make_AddTorrentJob):
    infos = [
        'Adding foo.torrent',
        '',
    ]

    def info_cb(_):
        assert job.info == infos.pop(0)

    job = make_AddTorrentJob()
    job.signal.register('adding', info_cb)
    job.signal.register('added', info_cb)
    job.signal.register('error', info_cb)
    job.signal.register('finished', info_cb)
    await job.handle_input('path/to/foo.torrent')
    assert infos == []

@pytest.mark.asyncio
async def test_handle_input_sets_info_property_on_failure(make_AddTorrentJob):
    infos = [
        'Adding foo.torrent',
        '',
        '',
    ]

    def info_cb(_):
        assert job.info == infos.pop(0)

    job = make_AddTorrentJob()
    job._client.add_torrent.side_effect = errors.RequestError('No')
    job.signal.register('adding', info_cb)
    job.signal.register('added', info_cb)
    job.signal.register('error', info_cb)
    job.signal.register('finished', info_cb)
    await job.handle_input('path/to/foo.torrent')
    assert infos == []
