import asyncio
import multiprocessing
import os
import time
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs.torrent import CreateTorrentJob, _torrent_process
from upsies.utils.daemon import MsgType


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


@pytest.fixture
def queues():
    queues = Mock(
        output=multiprocessing.Queue(),
        input=multiprocessing.Queue(),
    )
    yield queues
    # Prevent BrokenPipeError tracebacks on stderr
    # https://bugs.python.org/issue35844
    time.sleep(0.1)
    queues.output.cancel_join_thread()
    queues.input.cancel_join_thread()


@patch('upsies.utils.torrent.create')
def test_torrent_process_creates_torrent(create_mock, queues):
    create_mock.return_value = 'path/to/foo.mkv.torrent'
    _torrent_process(queues.output, queues.input, some='argument', another='one')
    assert queues.output.get() == (MsgType.result, 'path/to/foo.mkv.torrent')
    assert queues.output.empty()
    assert queues.input.empty()
    assert create_mock.call_args_list == [call(
        init_callback=Callable(),
        progress_callback=Callable(),
        some='argument',
        another='one',
    )]

@patch('upsies.utils.torrent.create')
def test_torrent_process_catches_TorrentError(create_mock, queues):
    create_mock.side_effect = errors.TorrentError('Argh')
    _torrent_process(queues.output, queues.input, some='argument')
    assert queues.output.get() == (MsgType.error, 'Argh')
    assert queues.output.empty()
    assert queues.input.empty()

def test_torrent_process_initializes_with_file_tree(mocker, queues):
    def create_mock(init_callback, **kwargs):
        init_callback('this is not a file tree')

    mocker.patch('upsies.utils.torrent.create', create_mock)
    _torrent_process(queues.output, queues.input, some='argument')
    assert queues.output.get() == (MsgType.init, 'this is not a file tree')

def test_torrent_process_sends_progress(mocker, queues):
    def create_mock(progress_callback, **kwargs):
        for progress in (10, 50, 100):
            progress_callback(progress)

    mocker.patch('upsies.utils.torrent.create', create_mock)
    _torrent_process(queues.output, queues.input, some='argument')
    assert queues.output.get() == (MsgType.info, 10)
    assert queues.output.get() == (MsgType.info, 50)
    assert queues.output.get() == (MsgType.info, 100)

def test_torrent_process_cancels_when_terminator_is_in_input_queue(mocker, queues):
    # sleep() and avoid joining any queue threads to avoid BrokenPipeError
    def create_mock(progress_callback, **kwargs):
        for i in range(1, 10):
            if i >= 5:
                queues.input.put((MsgType.terminate, None))
            if progress_callback(i):
                break
            time.sleep(0.1)
        return 'mocked result'

    mocker.patch('upsies.utils.torrent.create', create_mock)
    _torrent_process(queues.output, queues.input, some='argument')
    info = []
    while not queues.output.empty():
        info.append(queues.output.get(timeout=0.5))
    assert (MsgType.info, 5) in info
    assert (MsgType.info, 9) not in info


@pytest.fixture
def tracker():
    tracker = Mock()
    tracker.configure_mock(
        name='AsdF',
        config={
            'announce' : 'http://foo.bar',
            'source'   : 'AsdF',
            'exclude'  : ('a', 'b'),
        },
    )
    return tracker

def test_CreateTorrentJob_cache_id(tmp_path, tracker):
    job = CreateTorrentJob(
        home_directory=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        tracker=tracker,
    )
    assert job.cache_id == 'AsdF'


@patch('upsies.jobs.torrent._torrent_process')
def test_CreateTorrentJob_initialize_sets_private_variables(torrent_process_mock, tracker, tmp_path):
    ctj = CreateTorrentJob(
        home_directory=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        tracker=tracker,
    )
    assert ctj._content_path == 'path/to/foo'
    assert ctj._torrent_path == f'{tmp_path / "foo"}.asdf.torrent'
    assert ctj._file_tree == ''

@patch('upsies.utils.daemon.DaemonProcess')
def test_CreateTorrentJob_initialize_creates_torrent_process(DaemonProcess_mock, tracker, tmp_path):
    ctj = CreateTorrentJob(
        home_directory=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        tracker=tracker,
    )
    assert DaemonProcess_mock.call_args_list == [call(
        name=ctj.name,
        target=_torrent_process,
        kwargs={
            'content_path' : 'path/to/foo',
            'torrent_path' : os.path.join(ctj.home_directory, 'foo.asdf.torrent'),
            'overwrite'    : False,
            'announce'     : 'http://foo.bar',
            'source'       : 'AsdF',
            'exclude'      : ('a', 'b'),
        },
        init_callback=ctj._handle_file_tree,
        info_callback=ctj._handle_progress_update,
        error_callback=ctj.error,
        finished_callback=ctj._handle_torrent_created,
    )]


@pytest.fixture
def job(tmp_path, tracker):
    DaemonProcess_mock = Mock(
        return_value=Mock(
            join=AsyncMock(),
        ),
    )
    with patch('upsies.utils.daemon.DaemonProcess', DaemonProcess_mock):
        return CreateTorrentJob(
            home_directory=tmp_path,
            ignore_cache=False,
            content_path='path/to/foo',
            tracker=tracker,
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
async def test_CreateTorrentJob_wait_joins_torrent_process(job):
    asyncio.get_event_loop().call_soon(job.finish)
    await job.wait()
    assert job._torrent_process.join.call_args_list == [call()]

@pytest.mark.asyncio
async def test_CreateTorrentJob_wait_can_be_called_multiple_times(job):
    asyncio.get_event_loop().call_soon(job.finish)
    await job.wait()
    await job.wait()


@patch('upsies.utils.fs.file_tree')
def test_handle_file_tree(file_tree_mock, job):
    assert job._file_tree == ''
    job._handle_file_tree('beautiful tree')
    assert job._file_tree is file_tree_mock.return_value
    assert file_tree_mock.call_args_list == [call('beautiful tree')]


def test_info(job):
    assert job.info is job._file_tree


def test_progress_update_handling(job):
    cb = Mock()
    job.signal.register('progress_update', cb)
    job._handle_progress_update(10)
    assert cb.call_args_list == [call(10)]
    job._handle_progress_update(50)
    assert cb.call_args_list == [call(10), call(50)]
    job._handle_progress_update(100)
    assert cb.call_args_list == [call(10), call(50), call(100)]


def test_torrent_created_handling(job):
    assert job.output == ()
    assert not job.is_finished
    job._handle_torrent_created('mock torrent')
    assert job.output == ('mock torrent',)
    assert job.is_finished
