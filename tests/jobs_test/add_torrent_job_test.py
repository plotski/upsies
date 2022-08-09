from unittest.mock import Mock, call

import pytest

from upsies.jobs.torrent import AddTorrentJob


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def client():
    class MockClient():
        name = 'mocksy'
        label = 'Mocksy'
        add = AsyncMock()

        def __repr__(self):
            return '<MockClient instance>'

    return MockClient()


@pytest.fixture
async def make_AddTorrentJob(tmp_path, client):
    def make_AddTorrentJob(download_path=tmp_path, check_after_add='<check_after_add>', torrents=()):
        return AddTorrentJob(
            home_directory=tmp_path,
            cache_directory=tmp_path,
            ignore_cache=False,
            client_api=client,
            download_path=download_path,
            check_after_add=check_after_add,
            enqueue=torrents,
        )
    return make_AddTorrentJob


def test_cache_id(make_AddTorrentJob):
    job = make_AddTorrentJob()
    assert job.cache_id is None


@pytest.mark.parametrize(
    argnames='signal, args, exp_info',
    argvalues=(
        ('adding', ('path/to.torrent',), 'Adding to.torrent'),
        ('added', ('ignored argument',), ''),
        ('finished', ('ignored argument',), ''),
        ('error', ('ignored argument',), ''),
    ),
    ids=lambda v: repr(v),
)
@pytest.mark.asyncio
async def test_info_property_is_set(signal, args, exp_info, make_AddTorrentJob):
    job = make_AddTorrentJob()
    job.info = 'foo!'
    assert job.info == 'foo!'
    job.signal.emit(signal, *args)
    assert job.info == exp_info


@pytest.mark.parametrize('success', (True, False))
@pytest.mark.parametrize(
    argnames='added, already_added, exp_infohash',
    argvalues=(
        (['added infohash'], [], 'added infohash'),
        ([], ['already added infohash'], 'already added infohash'),
    ),
)
@pytest.mark.asyncio
async def test_handle_input(added, already_added, exp_infohash, success, make_AddTorrentJob, mocker):
    job = make_AddTorrentJob()
    mocks = Mock()

    response = Mock(
        success=success,
        added=added,
        already_added=already_added,
        warnings=['this is a warning'],
        errors=['first error', 'second error'],
    )
    mocks.add = AsyncMock(return_value=response)

    mocker.patch.object(job._client_api, 'add', mocks.add)
    mocker.patch.object(job, 'error', mocks.error)
    mocker.patch.object(job, 'warn', mocks.warn)
    mocker.patch.object(job, 'send', mocks.send)

    job.signal.register('adding', mocks.adding)
    job.signal.register('added', mocks.added)

    await job.handle_input('foo.torrent')
    exp_mock_calls = [
        call.adding('foo.torrent'),
        call.add(
            'foo.torrent',
            location=job._download_path,
            verify=job._check_after_add,
        ),
        call.warn('this is a warning'),
        call.error('first error'),
        call.error('second error'),
    ]
    if success:
        exp_mock_calls.extend([
            call.send(exp_infohash),
            call.added(exp_infohash),
        ])
    assert mocks.mock_calls == exp_mock_calls
