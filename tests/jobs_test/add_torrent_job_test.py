import asyncio
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs.torrent import AddTorrentJob
from upsies.tools import btclient


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


def run_async(awaitable):
    return asyncio.get_event_loop().run_until_complete(awaitable)


@pytest.fixture
def client(tmp_path):
    class MockClient(btclient.ClientApiBase):
        name = 'mocksy'
        add_torrent = AsyncMock()

        def __repr__(self):
            return '<MockClient instance>'

    return MockClient()

@pytest.fixture
async def make_AddTorrentJob(tmp_path, client):
    def make_AddTorrentJob(download_path=None, torrents=()):
        return AddTorrentJob(
            homedir=tmp_path,
            ignore_cache=False,
            client=client,
            download_path=download_path,
            torrents=torrents,
        )
    return make_AddTorrentJob


@patch('asyncio.ensure_future', Mock())
@patch('upsies.jobs.torrent.AddTorrentJob._add_torrents', Mock())
def test_cache_file_is_None(make_AddTorrentJob):
    job = make_AddTorrentJob()
    assert job.cache_file is None


@patch('asyncio.ensure_future')
@patch('upsies.jobs.torrent.AddTorrentJob._add_torrents', new_callable=Mock)
def test_initialize_with_torrents_argument(add_torrents_mock, ensure_future_mock, make_AddTorrentJob):
    job = make_AddTorrentJob(
        torrents=('foo.torrent', 'bar.torrent'),
        download_path='some/path',
    )
    queued_torrents = [job._torrent_path_queue.get_nowait() for _ in range(3)]
    assert queued_torrents == [('foo.torrent', 'some/path'),
                               ('bar.torrent', 'some/path'),
                               (None, None)]
    assert add_torrents_mock.call_args_list == [call()]
    assert job._add_torrents_task == ensure_future_mock.return_value
    assert ensure_future_mock.call_args_list == [call(add_torrents_mock.return_value)]

@patch('asyncio.ensure_future')
@patch('upsies.jobs.torrent.AddTorrentJob._add_torrents', new_callable=Mock)
def test_initialize_without_torrents_argument(add_torrents_mock, ensure_future_mock, make_AddTorrentJob):
    job = make_AddTorrentJob(
        download_path='some/path',
    )
    with pytest.raises(asyncio.QueueEmpty):
        job._torrent_path_queue.get_nowait()
    assert add_torrents_mock.call_args_list == [call()]
    assert job._add_torrents_task == ensure_future_mock.return_value
    assert ensure_future_mock.call_args_list == [call(add_torrents_mock.return_value)]


@patch('asyncio.ensure_future', Mock())
@patch('upsies.jobs.torrent.AddTorrentJob._add_torrents', Mock())
def test_finish_sends_termination_sentinel(make_AddTorrentJob):
    job = make_AddTorrentJob()
    with pytest.raises(asyncio.QueueEmpty):
        job._torrent_path_queue.get_nowait()
    job.finish()
    assert job._torrent_path_queue.get_nowait() == (None, None)
    assert not job.is_finished


@pytest.mark.asyncio
async def test_wait(make_AddTorrentJob):
    job = make_AddTorrentJob()
    assert not job._add_torrents_task.done()
    asyncio.get_event_loop().call_soon(job.finish())
    await job.wait()
    assert job._add_torrents_task.done()
    assert job.is_finished


@patch('asyncio.ensure_future', Mock())
@patch('upsies.jobs.torrent.AddTorrentJob._add_torrents', Mock())
def test_pipe_input_adds_argument(make_AddTorrentJob):
    job = make_AddTorrentJob()
    with patch.object(job, 'add') as add_mock:
        job.pipe_input('foo.torrent')
        assert add_mock.call_args_list == [call('foo.torrent')]


@patch('asyncio.ensure_future', Mock())
@patch('upsies.jobs.torrent.AddTorrentJob._add_torrents', Mock())
def test_pipe_closed_sends_termination_sentinel(make_AddTorrentJob):
    job = make_AddTorrentJob()
    with pytest.raises(asyncio.QueueEmpty):
        job._torrent_path_queue.get_nowait()
    job.pipe_closed()
    assert job._torrent_path_queue.get_nowait() == (None, None)
    assert not job.is_finished


@patch('asyncio.ensure_future', Mock())
@patch('upsies.jobs.torrent.AddTorrentJob._add_torrents', Mock())
@pytest.mark.parametrize(
    argnames='download_path, custom_download_path, exp_download_path',
    argvalues=(
        (None, None, None),
        ('some/path', None, 'some/path'),
        ('some/path', 'other/path', 'other/path'),
        (None, 'other/path', 'other/path'),
    ),
)
def test_add(download_path, custom_download_path, exp_download_path, make_AddTorrentJob):
    job = make_AddTorrentJob(download_path=download_path)
    job.add('foo.torrent', download_path=custom_download_path)
    assert job._torrent_path_queue.get_nowait() == ('foo.torrent', exp_download_path)


@patch('asyncio.ensure_future', Mock())
@patch('upsies.jobs.torrent.AddTorrentJob._add_torrents', Mock())
@pytest.mark.asyncio
async def test_add_async_call_order(make_AddTorrentJob):
    job = make_AddTorrentJob()
    cb = Mock()
    job.signal.register('adding', cb.adding)
    job.signal.register('added', cb.added)
    cb.add_torrent = AsyncMock(return_value=123)
    job._client.add_torrent = cb.add_torrent
    await job.add_async('foo.torrent')
    assert cb.mock_calls == [
        call.adding('foo.torrent'),
        call.add_torrent(torrent_path='foo.torrent', download_path=None),
        call.added(123),
    ]

@patch('asyncio.ensure_future', Mock())
@patch('upsies.jobs.torrent.AddTorrentJob._add_torrents', Mock())
@pytest.mark.asyncio
async def test_add_async_complains_about_large_torrent_file(make_AddTorrentJob, tmp_path):
    torrent_file = tmp_path / 'foo.torrent'
    f = open(torrent_file, 'wb')
    f.truncate(AddTorrentJob.MAX_TORRENT_SIZE + 1)  # Sparse file
    f.close()
    job = make_AddTorrentJob()
    await job.add_async(torrent_file)
    assert job.errors == (f'{torrent_file}: File is too large',)
    assert job.output == ()

@patch('asyncio.ensure_future', Mock())
@patch('upsies.jobs.torrent.AddTorrentJob._add_torrents', Mock())
@pytest.mark.asyncio
async def test_add_async_catches_TorrentError(make_AddTorrentJob):
    job = make_AddTorrentJob()
    job._client.add_torrent.side_effect = errors.TorrentError('No such file')
    await job.add_async('foo.torrent')
    assert job.errors == (
        'Failed to add foo.torrent to mocksy: No such file',
    )
    assert job.output == ()

@patch('asyncio.ensure_future', Mock())
@patch('upsies.jobs.torrent.AddTorrentJob._add_torrents', Mock())
@pytest.mark.asyncio
async def test_add_async_sends_torrent_id(make_AddTorrentJob):
    job = make_AddTorrentJob()
    job._client.add_torrent.return_value = '12345'
    await job.add_async('foo.torrent')
    assert job.output == ('12345',)
    assert job.errors == ()


@patch('asyncio.ensure_future', Mock())
@patch('upsies.jobs.torrent.AddTorrentJob.initialize', Mock())
@patch('upsies.jobs.torrent.AddTorrentJob.add_async', new_callable=AsyncMock)
def test_add_torrents(add_async_mock, make_AddTorrentJob):
    job = make_AddTorrentJob()
    job._torrent_path_queue = asyncio.Queue()
    job._torrent_path_queue.put_nowait(('foo.torrent', None))
    job._torrent_path_queue.put_nowait(('bar.torrent', 'some/path'))
    job._torrent_path_queue.put_nowait((None, None))
    run_async(job._add_torrents())
    assert add_async_mock.call_args_list == [
        call('foo.torrent', None),
        call('bar.torrent', 'some/path'),
    ]
