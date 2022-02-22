import fnmatch
import multiprocessing
import os
import re
import time
from unittest.mock import Mock, PropertyMock, call, patch

import pytest

from upsies import errors
from upsies.jobs.torrent import CreateTorrentJob, _torrent_process
from upsies.utils.daemon import MsgType
from upsies.utils.torrent import CreateTorrentProgress


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
        info_callback=Callable(),
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

def test_torrent_process_sends_info(mocker, queues):
    def create_mock(info_callback, **kwargs):
        for msg in ('a', 'b', 'c'):
            info_callback(msg)

    mocker.patch('upsies.utils.torrent.create', create_mock)
    _torrent_process(queues.output, queues.input, some='argument')
    assert queues.output.get() == (MsgType.info, 'a')
    assert queues.output.get() == (MsgType.info, 'b')
    assert queues.output.get() == (MsgType.info, 'c')

@pytest.mark.parametrize(
    argnames='callback_name, exp_msg_type',
    argvalues=(
        ('init_callback', MsgType.init),
        ('progress_callback', MsgType.info),
        ('info_callback', MsgType.info),
    ),
)
def test_torrent_process_cancels_when_terminator_is_in_input_queue(callback_name, exp_msg_type, mocker, queues):
    # sleep() and avoid joining any queue threads to avoid BrokenPipeError
    def create_mock(**kwargs):
        callback = kwargs[callback_name]
        for i in range(1, 10):
            if i >= 3:
                queues.input.put((MsgType.info, None))
            if i >= 5:
                queues.input.put((MsgType.terminate, None))
            if callback(i):
                break
            time.sleep(0.1)
        return 'mocked result'

    mocker.patch('upsies.utils.torrent.create', create_mock)
    _torrent_process(queues.output, queues.input, some='argument')
    info = []
    while not queues.output.empty():
        info.append(queues.output.get(timeout=0.5))
    assert (exp_msg_type, 5) in info
    assert (exp_msg_type, 9) not in info


@pytest.fixture
def tracker():
    tracker = Mock()
    tracker.configure_mock(
        name='AsdF',
        options={
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
        cache_directory=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        tracker=tracker,
    )
    assert job.cache_id is None


def test_CreateTorrentJob_initialize(tracker, tmp_path):
    job = CreateTorrentJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        reuse_torrent_path='path/to/existing.torrent',
        tracker=tracker,
    )
    assert job._content_path == 'path/to/foo'
    assert job._torrent_path == f'{tmp_path / "foo"}.asdf.torrent'
    assert job._exclude_files == list(tracker.options['exclude'])
    assert job._reuse_torrent_path == 'path/to/existing.torrent'
    assert job.info == ''
    assert job._torrent_process is None

@pytest.mark.parametrize(
    argnames='exclude_defaults, exclude_files, exp_exclude_files',
    argvalues=(
        ([r'.*\.txt$'], ['*.jpg'], [r'.*\.txt$', fnmatch.translate('*.jpg')]),
        ([r'.*\.txt$'], [re.compile(r'\.jpg$')], [r'.*\.txt$', re.compile(r'\.jpg$')]),
    ),
)
def test_CreateTorrentJob_initialize_with_exclude_files(exclude_defaults, exclude_files, exp_exclude_files,
                                                        tracker, tmp_path, mocker):
    mocker.patch.dict(tracker.options, {'exclude': exclude_defaults})
    job = CreateTorrentJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        tracker=tracker,
        exclude_files=exclude_files,
    )
    assert job._exclude_files == list(exp_exclude_files)


@pytest.fixture
def job(tmp_path, tracker):
    return CreateTorrentJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        reuse_torrent_path='path/to/existing.torrent',
        tracker=tracker,
    )

@pytest.mark.parametrize(
    argnames='ignore_cache, path_exists, exp_torrent_created',
    argvalues=(
        (False, False, True),
        (False, True, False),
        (True, False, True),
        (True, True, True),
    ),
)
@pytest.mark.asyncio
async def test_CreateTorrentJob_execute(ignore_cache, path_exists, exp_torrent_created, job, mocker, tmp_path):
    mocker.patch.object(job, '_get_announce_url', AsyncMock())
    mocker.patch.object(job, '_handle_torrent_created', Mock())
    mocker.patch.object(job, '_start_torrent_creation_process', Mock())
    mocker.patch.object(type(job), 'ignore_cache', PropertyMock(return_value=ignore_cache))

    if path_exists:
        (tmp_path / job._torrent_path).write_bytes(b'mock torrent data')

    job.execute()
    if hasattr(job, '_get_announce_url_task'):
        await job._get_announce_url_task

    if exp_torrent_created:
        assert job._get_announce_url.call_args_list == [call()]
        assert job._handle_torrent_created.call_args_list == []
        assert job._start_torrent_creation_process.call_args_list == [call(job._get_announce_url.return_value)]
        assert not job.is_finished
    else:
        assert job._get_announce_url.call_args_list == []
        assert job._handle_torrent_created.call_args_list == [call(job._torrent_path)]
        assert job._start_torrent_creation_process.call_args_list == []
        assert job.is_finished


@pytest.mark.asyncio
async def test_CreateTorrentJob_get_announce_url(job, mocker):
    mocks = AsyncMock(
        get_announce_url=AsyncMock(return_value='http://announce.url'),
        announce_url_callback=Mock(),
    )
    mocker.patch.object(job._tracker, 'login', mocks.login)
    mocker.patch.object(job._tracker, 'logout', mocks.logout)
    mocker.patch.object(job._tracker, 'get_announce_url', mocks.get_announce_url)
    job.signal.register('announce_url', mocks.announce_url_callback)

    assert job.info == ''
    announce_url = await job._get_announce_url()
    assert announce_url == mocks.get_announce_url.return_value
    assert mocks.mock_calls == [
        call.announce_url_callback(Ellipsis),
        call.login(),
        call.get_announce_url(),
        call.announce_url_callback('http://announce.url'),
        call.logout(),
    ]
    assert job.info == ''

@pytest.mark.asyncio
async def test_CreateTorrentJob_get_announce_url_catches_RequestError_from_login(job, mocker):
    mocks = AsyncMock(
        get_announce_url=AsyncMock(return_value='http://announce.url'),
        login=AsyncMock(side_effect=errors.RequestError('connection failed')),
        announce_url_callback=Mock(),
    )
    mocker.patch.object(job._tracker, 'login', mocks.login)
    mocker.patch.object(job._tracker, 'logout', mocks.logout)
    mocker.patch.object(job._tracker, 'get_announce_url', mocks.get_announce_url)
    job.signal.register('announce_url', mocks.announce_url_callback)

    assert job.info == ''
    announce_url = await job._get_announce_url()
    assert announce_url is None
    assert mocks.mock_calls == [
        call.announce_url_callback(Ellipsis),
        call.login(),
        call.logout(),
    ]
    assert job.errors == (errors.RequestError('connection failed'),)
    assert job.is_finished
    assert job.info == ''

@pytest.mark.asyncio
async def test_CreateTorrentJob_get_announce_url_catches_RequestError_from_get_announce_url(job, mocker):
    mocks = AsyncMock(
        get_announce_url=AsyncMock(side_effect=errors.RequestError('no url found')),
        announce_url_callback=Mock(),
    )
    mocker.patch.object(job._tracker, 'login', mocks.login)
    mocker.patch.object(job._tracker, 'logout', mocks.logout)
    mocker.patch.object(job._tracker, 'get_announce_url', mocks.get_announce_url)
    job.signal.register('announce_url', mocks.announce_url_callback)

    assert job.info == ''
    announce_url = await job._get_announce_url()
    assert announce_url is None
    assert mocks.mock_calls == [
        call.announce_url_callback(Ellipsis),
        call.login(),
        call.get_announce_url(),
        call.logout(),
    ]
    assert job.errors == (errors.RequestError('no url found'),)
    assert job.is_finished
    assert job.info == ''

@pytest.mark.asyncio
async def test_CreateTorrentJob_get_announce_url_catches_RequestError_from_logout(job, mocker):
    mocks = AsyncMock(
        get_announce_url=AsyncMock(return_value='http://announce.url'),
        logout=AsyncMock(side_effect=errors.RequestError('connection failed')),
        announce_url_callback=Mock(),
    )
    mocker.patch.object(job._tracker, 'login', mocks.login)
    mocker.patch.object(job._tracker, 'logout', mocks.logout)
    mocker.patch.object(job._tracker, 'get_announce_url', mocks.get_announce_url)
    job.signal.register('announce_url', mocks.announce_url_callback)

    assert job.info == ''
    announce_url = await job._get_announce_url()
    assert announce_url == mocks.get_announce_url.return_value
    assert mocks.mock_calls == [
        call.announce_url_callback(Ellipsis),
        call.login(),
        call.get_announce_url(),
        call.announce_url_callback('http://announce.url'),
        call.logout(),
    ]
    assert job.warnings == ('connection failed',)
    assert not job.is_finished
    assert job.info == ''


def test_CreateTorrentJob_start_torrent_creation_process(job, mocker):
    DaemonProcess_mock = mocker.patch('upsies.utils.daemon.DaemonProcess', Mock(
        return_value=Mock(join=AsyncMock()),
    ))
    announce_url = 'http:/foo/announce'
    job._start_torrent_creation_process(announce_url)
    assert DaemonProcess_mock.call_args_list == [call(
        name=job.name,
        target=_torrent_process,
        kwargs={
            'content_path': 'path/to/foo',
            'torrent_path': os.path.join(
                job.home_directory,
                f'foo.{job._tracker.options["source"].lower()}.torrent',
            ),
            'reuse_torrent_path': job._reuse_torrent_path,
            'overwrite': False,
            'announce': announce_url,
            'source': job._tracker.options['source'],
            'exclude': job._exclude_files,
        },
        init_callback=job._handle_file_tree,
        info_callback=job._handle_info_update,
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


def test_CreateTorrentJob_handle_file_tree(job):
    cb = Mock()
    job.signal.register('file_tree', cb)
    assert cb.call_args_list == []
    job._handle_file_tree('nested file tree sequence')
    assert cb.call_args_list == [call('nested file tree sequence')]


def test_CreateTorrentJob_handle_info_update_handles_CreateTorrentProgress(job):
    cb = Mock()
    job.signal.register('progress_update', cb)
    job._handle_info_update(CreateTorrentProgress(
        bytes_per_second='mock bytes_per_second',
        filepath='mock filepath',
        percent_done='mock percent_done',
        piece_size='mock piece_size',
        pieces_done='mock pieces_done',
        pieces_total='mock pieces_total',
        seconds_elapsed='mock seconds_elapsed',
        seconds_remaining='mock seconds_remaining',
        seconds_total='mock seconds_total',
        time_finished='mock time_finished',
        time_started='mock time_started',
        total_size='mock total_size',
    ))
    assert cb.call_args_list == [call(CreateTorrentProgress(
        bytes_per_second='mock bytes_per_second',
        filepath='mock filepath',
        percent_done='mock percent_done',
        piece_size='mock piece_size',
        pieces_done='mock pieces_done',
        pieces_total='mock pieces_total',
        seconds_elapsed='mock seconds_elapsed',
        seconds_remaining='mock seconds_remaining',
        seconds_total='mock seconds_total',
        time_finished='mock time_finished',
        time_started='mock time_started',
        total_size='mock total_size',
    ))]
    job._handle_info_update('This is a message.')
    assert cb.call_args_list == [call(CreateTorrentProgress(
        bytes_per_second='mock bytes_per_second',
        filepath='mock filepath',
        percent_done='mock percent_done',
        piece_size='mock piece_size',
        pieces_done='mock pieces_done',
        pieces_total='mock pieces_total',
        seconds_elapsed='mock seconds_elapsed',
        seconds_remaining='mock seconds_remaining',
        seconds_total='mock seconds_total',
        time_finished='mock time_finished',
        time_started='mock time_started',
        total_size='mock total_size',
    ))]


@pytest.mark.parametrize(
    argnames='torrent_path, exp_output',
    argvalues=(
        (None, ()),
        ('', ()),
        ('foo/bar.torrent', ('foo/bar.torrent',),),
    ),
)
def test_CreateTorrentJob_handle_torrent_created(torrent_path, exp_output, job):
    assert job.output == ()
    job._handle_torrent_created(torrent_path)
    assert job.output == exp_output


def test_CreateTorrentJob_handle_error(job, mocker):
    mocker.patch.object(job, 'exception')
    mocker.patch.object(job, 'error')
    job._handle_error('message')
    assert job.error.call_args_list == [call('message')]
    job._handle_error(errors.RequestError('message'))
    assert job.exception.call_args_list == [call(errors.RequestError('message'))]
