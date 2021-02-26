import asyncio
import multiprocessing
import os
import re
import time
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs.torrent import CreateTorrentJob, _torrent_process
from upsies.utils.daemon import MsgType


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


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
            'source'   : 'AsdF',
            'exclude'  : ('a', 'b'),
        },
        with_login=AsyncMock(),
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


def test_CreateTorrentJob_initialize(tracker, tmp_path):
    job = CreateTorrentJob(
        home_directory=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        tracker=tracker,
    )
    assert job._content_path == 'path/to/foo'
    assert job._torrent_path == f'{tmp_path / "foo"}.asdf.torrent'
    assert job._file_tree == ''
    assert job._announce_url_task is None
    assert job._torrent_process is None


@pytest.fixture
def job(tmp_path, tracker):
    return CreateTorrentJob(
        home_directory=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        tracker=tracker,
    )


@pytest.mark.parametrize(
    argnames='raised_exception, exp_errors, exp_exc',
    argvalues=(
        (None, (), None),
        (errors.RequestError('foo'), (errors.RequestError('foo'),), None),
        (TypeError('foo'), (), TypeError('foo')),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_CreateTorrentJob_execute(raised_exception, exp_errors, exp_exc, job, mocker):
    if raised_exception:
        mocker.patch.object(job._tracker, 'with_login', AsyncMock(side_effect=raised_exception))
    else:
        mocker.patch.object(job._tracker, 'with_login', AsyncMock(return_value='http://announce'))
    mocker.patch.object(job._tracker, 'get_announce_url', Mock(return_value='coroutine mock'))
    mocker.patch.object(job, '_create_torrent_process', Mock())
    job.execute()
    asyncio.get_event_loop().call_later(0.5, job.finish)
    if exp_exc:
        with pytest.raises(type(exp_exc), match=rf'^{re.escape(str(exp_exc))}$'):
            await job.wait()
    else:
        await job.wait()
    assert job.errors == exp_errors
    assert job._tracker.get_announce_url.call_args_list == [call()]
    assert job._tracker.with_login.call_args_list == [call('coroutine mock')]
    if raised_exception:
        assert job._create_torrent_process.call_args_list == []
    else:
        assert job._create_torrent_process.call_args_list == [call('http://announce')]


def test_CreateTorrentJob_create_torrent_process(job, mocker):
    DaemonProcess_mock = mocker.patch('upsies.utils.daemon.DaemonProcess', Mock(
        return_value=Mock(join=AsyncMock()),
    ))
    announce_url = 'http:/foo/announce'
    job._create_torrent_process(announce_url)
    assert DaemonProcess_mock.call_args_list == [call(
        name=job.name,
        target=_torrent_process,
        kwargs={
            'content_path' : 'path/to/foo',
            'torrent_path' : os.path.join(
                job.home_directory,
                f'foo.{job._tracker.config["source"].lower()}.torrent',
            ),
            'overwrite'    : False,
            'announce'     : announce_url,
            'source'       : job._tracker.config['source'],
            'exclude'      : job._tracker.config['exclude'],
        },
        init_callback=job._handle_file_tree,
        info_callback=job._handle_progress_update,
        error_callback=job.error,
        finished_callback=job._handle_torrent_created,
    )]
    assert job._torrent_process.start.call_args_list == [call()]


@pytest.mark.parametrize(
    argnames='torrent_process, announce_url_task',
    argvalues=(
        (None, None),
        (None, Mock()),
        (Mock(), None),
        (Mock(), Mock()),
    ),
)
def test_CreateTorrentJob_finish(torrent_process, announce_url_task, job):
    job._torrent_process = torrent_process
    job._announce_url_task = announce_url_task
    assert not job.is_finished
    job.finish()
    assert job.is_finished
    if torrent_process:
        assert job._torrent_process.stop.call_args_list == [call()]
    else:
        assert job._torrent_process is None
    if announce_url_task:
        assert job._announce_url_task.cancel.call_args_list == [call()]
    else:
        assert job._announce_url_task is None


@pytest.mark.parametrize('torrent_process', (None, Mock(join=AsyncMock())))
@pytest.mark.asyncio
async def test_CreateTorrentJob_wait_joins_torrent_process(torrent_process, job):
    job._torrent_process = torrent_process
    asyncio.get_event_loop().call_soon(job.finish)
    await job.wait()
    if torrent_process:
        assert job._torrent_process.join.call_args_list == [call()]
    else:
        assert job._torrent_process is None

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
