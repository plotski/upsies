import multiprocessing
import os
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
        login=AsyncMock(),
        get_announce_url=AsyncMock(),
        logout=AsyncMock(),
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
    assert job.info == ''
    assert job._torrent_process is None


@pytest.fixture
def job(tmp_path, tracker):
    return CreateTorrentJob(
        home_directory=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        tracker=tracker,
    )


def test_CreateTorrentJob_execute(job, mocker):
    mocker.patch.object(job, 'add_task')
    mocker.patch.object(job, '_get_announce_url', Mock())
    job.execute()
    assert job._get_announce_url.call_args_list == [call()]
    assert job.add_task.call_args_list == [call(job._get_announce_url.return_value)]


@pytest.mark.asyncio
async def test_CreateTorrentJob_get_announce_url_creates_torrent_process(job, mocker):
    def create_torrent_process_mock(announce_url):
        assert job.info == 'Getting announce URL...'

    mocks = AsyncMock(
        create_torrent_process=Mock(side_effect=create_torrent_process_mock),
        get_announce_url=AsyncMock(return_value='http://announce.url'),
    )
    mocker.patch.object(job._tracker, 'login', mocks.login)
    mocker.patch.object(job._tracker, 'logout', mocks.logout)
    mocker.patch.object(job._tracker, 'get_announce_url', mocks.get_announce_url)
    mocker.patch.object(job, '_create_torrent_process', mocks.create_torrent_process)

    assert job.info == ''
    await job._get_announce_url()
    assert mocks.mock_calls == [
        call.login(),
        call.get_announce_url(),
        call.create_torrent_process('http://announce.url'),
        call.logout(),
    ]
    assert job.info == ''

@pytest.mark.asyncio
async def test_CreateTorrentJob_get_announce_url_catches_RequestError_from_login(job, mocker):
    def create_torrent_process_mock(announce_url):
        assert job.info == 'Getting announce URL...'

    mocks = AsyncMock(
        create_torrent_process=Mock(side_effect=create_torrent_process_mock),
        get_announce_url=AsyncMock(return_value='http://announce.url'),
        login=AsyncMock(side_effect=errors.RequestError('connection failed')),
    )
    mocker.patch.object(job._tracker, 'login', mocks.login)
    mocker.patch.object(job._tracker, 'logout', mocks.logout)
    mocker.patch.object(job._tracker, 'get_announce_url', mocks.get_announce_url)
    mocker.patch.object(job, '_create_torrent_process', mocks.create_torrent_process)

    assert job.info == ''
    await job._get_announce_url()
    assert mocks.mock_calls == [
        call.login(),
        call.logout(),
    ]
    assert job.errors == (errors.RequestError('connection failed'),)
    assert job.is_finished
    assert job.info == ''

@pytest.mark.asyncio
async def test_CreateTorrentJob_get_announce_url_catches_RequestError_from_get_announce_url(job, mocker):
    def create_torrent_process_mock(announce_url):
        assert job.info == 'Getting announce URL...'

    mocks = AsyncMock(
        create_torrent_process=Mock(side_effect=create_torrent_process_mock),
        get_announce_url=AsyncMock(side_effect=errors.RequestError('no url found')),
    )
    mocker.patch.object(job._tracker, 'login', mocks.login)
    mocker.patch.object(job._tracker, 'logout', mocks.logout)
    mocker.patch.object(job._tracker, 'get_announce_url', mocks.get_announce_url)
    mocker.patch.object(job, '_create_torrent_process', mocks.create_torrent_process)

    assert job.info == ''
    await job._get_announce_url()
    assert mocks.mock_calls == [
        call.login(),
        call.get_announce_url(),
        call.logout(),
    ]
    assert job.errors == (errors.RequestError('no url found'),)
    assert job.is_finished
    assert job.info == ''

@pytest.mark.asyncio
async def test_CreateTorrentJob_get_announce_url_catches_RequestError_from_logout(job, mocker):
    def create_torrent_process_mock(announce_url):
        assert job.info == 'Getting announce URL...'

    mocks = AsyncMock(
        create_torrent_process=Mock(side_effect=create_torrent_process_mock),
        get_announce_url=AsyncMock(return_value='http://announce.url'),
        logout=AsyncMock(side_effect=errors.RequestError('connection failed')),
    )
    mocker.patch.object(job._tracker, 'login', mocks.login)
    mocker.patch.object(job._tracker, 'logout', mocks.logout)
    mocker.patch.object(job._tracker, 'get_announce_url', mocks.get_announce_url)
    mocker.patch.object(job, '_create_torrent_process', mocks.create_torrent_process)

    assert job.info == ''
    await job._get_announce_url()
    assert mocks.mock_calls == [
        call.login(),
        call.get_announce_url(),
        call.create_torrent_process('http://announce.url'),
        call.logout(),
    ]
    assert job.warnings == (errors.RequestError('connection failed'),)
    assert not job.is_finished
    assert job.info == ''


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
        error_callback=job._handle_error,
        result_callback=job._handle_torrent_created,
        finished_callback=job.finish,
    )]
    assert job._torrent_process.start.call_args_list == [call()]


@pytest.mark.parametrize('torrent_process', (None, Mock()))
def test_CreateTorrentJob_finish(torrent_process, job):
    job._torrent_process = torrent_process
    assert not job.is_finished
    job.finish()
    assert job.is_finished
    if torrent_process:
        assert job._torrent_process.stop.call_args_list == [call()]
    else:
        assert job._torrent_process is None


@patch('upsies.utils.fs.file_tree')
def test_handle_file_tree(file_tree_mock, job):
    assert job.info == ''
    job._handle_file_tree('beautiful tree')
    assert job.info == str(file_tree_mock.return_value)
    assert file_tree_mock.call_args_list == [call('beautiful tree')]


def test_handle_progress_update(job):
    cb = Mock()
    job.signal.register('progress_update', cb)
    job._handle_progress_update(10)
    assert cb.call_args_list == [call(10)]
    job._handle_progress_update(50)
    assert cb.call_args_list == [call(10), call(50)]
    job._handle_progress_update(100)
    assert cb.call_args_list == [call(10), call(50), call(100)]


@pytest.mark.parametrize(
    argnames='torrent_path, exp_output',
    argvalues=(
        (None, ()),
        ('', ()),
        ('foo/bar.torrent', ('foo/bar.torrent',),),
    ),
)
def test_handle_torrent_created(torrent_path, exp_output, job):
    assert job.output == ()
    job._handle_torrent_created(torrent_path)
    assert job.output == exp_output


def test_handle_error(job, mocker):
    mocker.patch.object(job, 'exception')
    mocker.patch.object(job, 'error')
    job._handle_error('message')
    assert job.error.call_args_list == [call('message')]
    job._handle_error(errors.RequestError('message'))
    assert job.exception.call_args_list == [call(errors.RequestError('message'))]
