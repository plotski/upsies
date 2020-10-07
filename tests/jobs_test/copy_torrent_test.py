from unittest.mock import Mock, call, patch

import pytest

from upsies.jobs.torrent import CopyTorrentJob


@pytest.fixture
async def make_CopyTorrentJob(tmp_path):
    def make_CopyTorrentJob(destination=None, files=()):
        return CopyTorrentJob(
            homedir=tmp_path,
            ignore_cache=False,
            destination=destination,
            files=files,
        )
    return make_CopyTorrentJob


def test_cache_file_is_None(make_CopyTorrentJob):
    job = make_CopyTorrentJob()
    assert job.cache_file is None


@patch('upsies.jobs.torrent.CopyTorrentJob.copy', Mock())
@pytest.mark.parametrize(
    argnames='destination, exp_destination',
    argvalues=(
        (None, None),
        ('', None),
        ('foo', 'foo'),
        (123, '123'),
    ),
)
def test_initialize_with_destination(destination, exp_destination, make_CopyTorrentJob):
    job = make_CopyTorrentJob(destination=destination)
    assert job._destination == exp_destination
    assert not job.is_finished

@patch('upsies.jobs.torrent.CopyTorrentJob.copy', Mock())
def test_initialize_without_files(make_CopyTorrentJob):
    job = make_CopyTorrentJob()
    assert job.copy.call_args_list == []
    assert not job.is_finished

@patch('upsies.jobs.torrent.CopyTorrentJob.copy')
@pytest.mark.parametrize(
    argnames='destination',
    argvalues=(None, '/foo/bar'),
)
def test_initialize_with_files(copy_mock, destination, make_CopyTorrentJob):
    job = make_CopyTorrentJob(files=('a.jpg', 'b.jpg'),
                              destination=destination)
    assert copy_mock.call_args_list == [
        call('a.jpg'),
        call('b.jpg'),
    ]
    assert job.is_finished


@patch('upsies.jobs.torrent.CopyTorrentJob.copy')
def test_pipe_input(copy_mock, make_CopyTorrentJob):
    job = make_CopyTorrentJob()
    job.copy('a.jpg')
    assert copy_mock.call_args_list == [
        call('a.jpg'),
    ]
    job.copy('b.jpg')
    assert copy_mock.call_args_list == [
        call('a.jpg'),
        call('b.jpg'),
    ]
    assert not job.is_finished


@patch('upsies.jobs.torrent.CopyTorrentJob.copy')
def test_pipe_output(copy_mock, make_CopyTorrentJob):
    job = make_CopyTorrentJob()
    assert not job.is_finished
    job.pipe_closed()
    assert job.is_finished


@patch('shutil.copy2')
def test_copy_on_finished_job(copy2_mock, make_CopyTorrentJob):
    job = make_CopyTorrentJob()
    job.finish()
    with pytest.raises(RuntimeError, match=r'CopyTorrentJob is already finished'):
        job.copy('foo')
    assert copy2_mock.call_args_list == []
    assert job.output == ()
    assert job.errors == ()
    assert job.is_finished

@patch('shutil.copy2')
def test_copy_without_destination(copy2_mock, make_CopyTorrentJob):
    job = make_CopyTorrentJob()
    with pytest.raises(RuntimeError, match=r'Cannot copy without destination'):
        job.copy('foo')
    assert copy2_mock.call_args_list == []
    assert job.output == ()
    assert job.errors == ()
    assert not job.is_finished

@patch('shutil.copy2')
def test_copy_nonexisting_file(copy2_mock, make_CopyTorrentJob):
    job = make_CopyTorrentJob(destination='foo')
    job.copy('bar')
    assert copy2_mock.call_args_list == []
    assert job.output == ()
    assert job.errors == ('bar: No such file',)
    assert not job.is_finished

@patch('shutil.copy2')
def test_copy_too_large_file(copy2_mock, tmp_path, make_CopyTorrentJob):
    filepath = tmp_path / 'foo.torrent'
    f = open(filepath, 'wb')
    f.truncate(CopyTorrentJob.MAX_FILE_SIZE + 1)  # Sparse file
    f.close()
    job = make_CopyTorrentJob(destination='foo')
    job.copy(filepath)
    assert copy2_mock.call_args_list == []
    assert job.output == ()
    assert job.errors == (f'{filepath}: File is too large',)
    assert not job.is_finished

@patch('shutil.copy2')
def test_copy_with_destination_from_initialize(copy2_mock, tmp_path, make_CopyTorrentJob):
    filepath = tmp_path / 'foo.torrent'
    filepath.write_bytes(b'metainfo')
    job = make_CopyTorrentJob(destination='foo')
    copy2_mock.return_value = 'destination/path'
    job.copy(filepath)
    assert copy2_mock.call_args_list == [call(filepath, 'foo')]
    assert job.output == (copy2_mock.return_value,)
    assert job.errors == ()
    assert not job.is_finished

@patch('shutil.copy2')
def test_copy_with_destination_from_argument(copy2_mock, tmp_path, make_CopyTorrentJob):
    filepath = tmp_path / 'foo.torrent'
    filepath.write_bytes(b'metainfo')
    job = make_CopyTorrentJob()
    copy2_mock.return_value = 'destination/path'
    job.copy(filepath, 'bar')
    assert copy2_mock.call_args_list == [call(filepath, 'bar')]
    assert job.output == (copy2_mock.return_value,)
    assert job.errors == ()
    assert not job.is_finished

@patch('shutil.copy2')
def test_copy_catches_OSError(copy2_mock, tmp_path, make_CopyTorrentJob):
    filepath = tmp_path / 'foo.torrent'
    filepath.write_bytes(b'metainfo')
    copy2_mock.side_effect = OSError('Do it yourself')
    job = make_CopyTorrentJob()
    job.copy(filepath, '/root')
    assert copy2_mock.call_args_list == [call(filepath, '/root')]
    assert job.output == (str(filepath),)
    assert job.errors == (f'Failed to copy {filepath} to /root: Do it yourself',)
    assert not job.is_finished
