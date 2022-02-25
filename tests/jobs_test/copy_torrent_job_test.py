from unittest.mock import Mock, call

import pytest

from upsies.jobs.torrent import CopyTorrentJob


@pytest.fixture
async def make_CopyTorrentJob(tmp_path):
    def make_CopyTorrentJob(destination, enqueue=()):
        return CopyTorrentJob(
            home_directory=tmp_path,
            cache_directory=tmp_path,
            ignore_cache=False,
            destination=destination,
            enqueue=enqueue,
        )
    return make_CopyTorrentJob


def test_cache_id(make_CopyTorrentJob, tmp_path):
    job = make_CopyTorrentJob(destination=tmp_path)
    assert job.cache_id is None


@pytest.mark.asyncio
async def test_handle_input_call_order(make_CopyTorrentJob, mocker, tmp_path):
    job = make_CopyTorrentJob(destination=tmp_path)

    filepath = tmp_path / 'foo.torrent'
    filepath.write_text('hello')

    mocks = Mock()
    job.signal.register('copying', mocks.copying)
    job.signal.register('copied', mocks.copied)
    copy2_mock = mocker.patch('shutil.copy2', return_value=str(tmp_path / filepath.name))
    mocks.attach_mock(copy2_mock, 'copy2')

    await job.handle_input(str(filepath))
    assert mocks.mock_calls == [
        call.copying(str(filepath)),
        call.copy2(str(filepath), str(tmp_path)),
        call.copied(copy2_mock.return_value),
    ]

@pytest.mark.asyncio
async def test_handle_input_reports_nonexisting_file(make_CopyTorrentJob, mocker, tmp_path):
    job = make_CopyTorrentJob(destination='foo')

    mocks = Mock()
    job.signal.register('copying', mocks.copying)
    job.signal.register('copied', mocks.copied)
    copy2_mock = mocker.patch('shutil.copy2')
    mocks.attach_mock(copy2_mock, 'copy2')

    await job.handle_input(tmp_path / 'foo')
    assert job.output == ()
    assert job.errors == (f'{tmp_path / "foo"}: No such file',)
    assert mocks.mock_calls == []

@pytest.mark.asyncio
async def test_copy_too_large_file(make_CopyTorrentJob, mocker, tmp_path):
    job = make_CopyTorrentJob(destination='foo')

    filepath = tmp_path / 'foo.torrent'
    with open(filepath, 'wb') as f:
        f.truncate(CopyTorrentJob.MAX_FILE_SIZE + 1)  # Sparse file

    mocks = Mock()
    job.signal.register('copying', mocks.copying)
    job.signal.register('copied', mocks.copied)
    copy2_mock = mocker.patch('shutil.copy2')
    mocks.attach_mock(copy2_mock, 'copy2')

    await job.handle_input(filepath)
    assert job.output == ()
    assert job.errors == (f'{filepath}: File is too large',)
    assert mocks.mock_calls == []

@pytest.mark.asyncio
async def test_handle_input_sends_destination_path_on_success(make_CopyTorrentJob, mocker, tmp_path):
    job = make_CopyTorrentJob(destination='foo')

    filepath = tmp_path / 'foo.torrent'
    filepath.write_bytes(b'content')

    mocker.patch('shutil.copy2', return_value='destination/path')

    await job.handle_input(filepath)
    assert job.output == ('destination/path',)
    assert job.errors == ()

@pytest.mark.asyncio
async def test_handle_input_sends_source_path_on_failure(make_CopyTorrentJob, mocker, tmp_path):
    job = make_CopyTorrentJob(destination='foo')

    filepath = tmp_path / 'foo.torrent'
    filepath.write_bytes(b'content')

    mocker.patch('shutil.copy2', side_effect=PermissionError('Permission denied'))

    await job.handle_input(filepath)
    assert job.output == ()
    assert job.errors == (f'Failed to copy {filepath} to {job._destination}: Permission denied',)

@pytest.mark.asyncio
async def test_handle_input_sets_info_property_on_success(make_CopyTorrentJob, mocker, tmp_path):
    job = make_CopyTorrentJob(destination='foo')

    filepath = tmp_path / 'foo.torrent'
    filepath.write_bytes(b'content')

    mocker.patch('shutil.copy2', return_value='destination/path')

    infos = [
        'Copying foo.torrent',
        '',
    ]

    def info_cb(_):
        assert job.info == infos.pop(0)

    job.signal.register('copying', info_cb)
    job.signal.register('copied', info_cb)
    job.signal.register('error', info_cb)
    job.signal.register('finished', info_cb)
    await job.handle_input(filepath)
    assert infos == []

@pytest.mark.asyncio
async def test_handle_input_sets_info_property_on_failure(make_CopyTorrentJob, mocker, tmp_path):
    job = make_CopyTorrentJob(destination='foo')

    filepath = tmp_path / 'foo.torrent'
    filepath.write_bytes(b'content')

    mocker.patch('shutil.copy2', side_effect=OSError('No'))

    infos = [
        'Copying foo.torrent',
        '',
        '',
    ]

    def info_cb(_):
        assert job.info == infos.pop(0)

    job.signal.register('copying', info_cb)
    job.signal.register('copied', info_cb)
    job.signal.register('error', info_cb)
    job.signal.register('finished', info_cb)
    await job.handle_input(filepath)
    assert infos == []
