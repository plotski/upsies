import asyncio
import multiprocessing
import os
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs._common import DaemonProcess
from upsies.jobs.torrent import CreateTorrentJob, _torrent_process


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


class Callable:
    def __eq__(self, other):
        return callable(other)


@patch('upsies.tools.torrent.create')
def test_torrent_process_creates_torrent(torrent_mock):
    output_queue = multiprocessing.Queue()
    input_queue = multiprocessing.Queue()
    torrent_mock.return_value = 'path/to/foo.mkv.torrent'
    _torrent_process(output_queue, input_queue, some='argument', another='one')
    assert output_queue.get() == (DaemonProcess.RESULT, 'path/to/foo.mkv.torrent')
    assert output_queue.empty()
    assert input_queue.empty()
    assert torrent_mock.call_args_list == [call(
        init_callback=Callable(),
        progress_callback=Callable(),
        some='argument',
        another='one',
    )]

@patch('upsies.tools.torrent.create')
def test_torrent_process_catches_TorrentError(torrent_mock):
    output_queue = multiprocessing.Queue()
    input_queue = multiprocessing.Queue()
    torrent_mock.side_effect = errors.TorrentError('Argh')
    _torrent_process(output_queue, input_queue, some='argument')
    assert output_queue.get() == (DaemonProcess.ERROR, 'Argh')
    assert output_queue.empty()
    assert input_queue.empty()


@patch('upsies.jobs.torrent._torrent_process')
def test_CreateTorrentJob_initialize_sets_variables(torrent_process_mock, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        tracker_name='ASDF',
        tracker_config={
            'announce' : 'http://foo.bar',
            'source'   : 'AsdF',
            'exclude'  : ('a', 'b'),
        },
    )
    assert ctj._content_path == 'path/to/foo'
    assert ctj._torrent_path == f'{tmp_path / "foo"}.asdf.torrent'
    assert ctj._file_tree == ''

@patch('upsies.jobs._common.DaemonProcess')
def test_CreateTorrentJob_initialize_creates_torrent_process(DaemonProcess_mock, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        tracker_name='ASDF',
        tracker_config={
            'announce' : 'http://foo.bar',
            'source'   : 'AsdF',
            'exclude'  : ('a', 'b'),
        },
    )
    assert DaemonProcess_mock.call_args_list == [call(
        name=ctj.name,
        target=_torrent_process,
        kwargs={
            'content_path' : 'path/to/foo',
            'torrent_path' : os.path.join(ctj.homedir, 'foo.asdf.torrent'),
            'overwrite'    : False,
            'announce'     : 'http://foo.bar',
            'source'       : 'AsdF',
            'exclude'      : ('a', 'b'),
        },
        init_callback=ctj.handle_file_tree,
        info_callback=ctj.handle_progress_update,
        error_callback=ctj.error,
        finished_callback=ctj.handle_torrent_created,
    )]


@pytest.fixture
def job(tmp_path):
    DaemonProcess_mock = Mock(
        return_value=Mock(
            join=AsyncMock(),
        ),
    )
    with patch('upsies.jobs._common.DaemonProcess', DaemonProcess_mock):
        return CreateTorrentJob(
            homedir=tmp_path,
            ignore_cache=False,
            content_path='path/to/foo',
            tracker_name='ASDF',
            tracker_config={
                'announce' : 'http://foo.bar',
                'source'   : 'AsdF',
                'exclude'  : ('a', 'b'),
            },
        )

def test_CreateTorrentJob_execute(job):
    assert job.execute() is None
    assert job._torrent_process.start.call_args_list == [call()]


def test_CreateTorrentJob_finish(job):
    assert not job.is_finished
    job.finish()
    assert job.is_finished
    assert job._torrent_process.stop.call_args_list == [call()]


@pytest.mark.asyncio
async def test_CreateTorrentJob_wait(job):
    assert not job.is_finished
    asyncio.get_event_loop().call_soon(job.finish)
    await job.wait()
    assert job.is_finished
    assert job._torrent_process.join.call_args_list == [call()]


@patch('upsies.utils.fs.file_tree')
def test_handle_file_tree(file_tree_mock, job):
    assert job._file_tree == ''
    job.handle_file_tree('beautiful tree')
    assert job._file_tree is file_tree_mock.return_value
    assert file_tree_mock.call_args_list == [call('beautiful tree')]


def test_info(job):
    assert job.info is job._file_tree


def test_progress_update_handling(job):
    cb = Mock()
    job.on_progress_update(cb)
    job.handle_progress_update(10)
    assert cb.call_args_list == [call(10)]
    job.handle_progress_update(50)
    assert cb.call_args_list == [call(10), call(50)]
    job.handle_progress_update(100)
    assert cb.call_args_list == [call(10), call(50), call(100)]


def test_torrent_created_handling(job):
    assert job.output == ()
    assert not job.is_finished
    job.handle_torrent_created('mock torrent')
    assert job.output == ('mock torrent',)
    assert job.is_finished
