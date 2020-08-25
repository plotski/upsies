import asyncio
import multiprocessing
import os
from unittest.mock import Mock, call, patch

try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock(Mock):
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)

from upsies import errors
from upsies.jobs._common import DaemonProcess
from upsies.jobs.torrent import CreateTorrentJob, _torrent_process


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
def test_CreateTorrentJob_initialize(torrent_process_mock, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
    )
    assert not ctj.is_finished
    assert ctj.info == ''
    assert torrent_process_mock.call_args_list == []


@patch('upsies.jobs._common.DaemonProcess')
def test_CreateTorrentJob_execute(process_mock, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
    )
    ctj.execute()
    assert not ctj.is_finished
    assert process_mock.call_args_list == [call(
        name=ctj.name,
        target=_torrent_process,
        kwargs={
            'content_path'   : 'path/to/foo',
            'torrent_path'   : os.path.join(tmp_path, 'foo.asdf.torrent'),
            'announce_url'   : 'http://foo.bar',
            'source'         : 'AsdF',
            'exclude_regexs' : ('a', 'b'),
        },
        init_callback=ctj.handle_file_tree,
        info_callback=ctj.handle_progress_update,
        error_callback=ctj.handle_error,
        finished_callback=ctj.handle_finished,
    )]
    assert process_mock.return_value.start.call_args_list == [call()]

@patch('upsies.jobs._common.DaemonProcess')
def test_CreateTorrentJob_finish(process_mock, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
    )
    ctj.execute()
    assert not ctj.is_finished
    ctj.finish()
    assert process_mock.return_value.stop.call_args_list == [call()]
    assert ctj.is_finished

@patch('upsies.jobs._common.DaemonProcess', return_value=Mock(join=AsyncMock()))
def test_CreateTorrentJob_wait(process_mock, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
    )
    ctj.execute()
    assert not ctj.is_finished
    asyncio.get_event_loop().call_soon(ctj.finish)
    asyncio.get_event_loop().run_until_complete(ctj.wait())
    assert process_mock.return_value.join.call_args_list == [call()]
    assert ctj.is_finished

def test_CreateTorrentJob_progress_update(tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
    )
    progress_update_cb = Mock()
    ctj.on_progress_update(progress_update_cb)
    ctj.handle_progress_update(10.5)
    assert progress_update_cb.call_args_list == [call(10.5)]
    ctj.handle_progress_update(50.123)
    assert progress_update_cb.call_args_list == [call(10.5), call(50.123)]
    assert not ctj.is_finished

def test_CreateTorrentJob_error(tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
    )
    error_cb = Mock()
    ctj.on_error(error_cb)
    ctj.handle_error('Nooo!')
    assert error_cb.call_args_list == [call('Nooo!')]
    assert ctj.errors == ('Nooo!',)
    assert not ctj.is_finished

def test_CreateTorrentJob_finished_successfully(tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
    )
    finished_cb = Mock()
    ctj.on_finished(finished_cb)
    ctj.handle_finished('path/to/torrent')
    assert finished_cb.call_args_list == [call('path/to/torrent')]
    assert ctj.output == ('path/to/torrent',)
    assert ctj.is_finished

def test_CreateTorrentJob_finished_unsuccessfully(tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
    )
    finished_cb = Mock()
    ctj.on_finished(finished_cb)
    ctj.handle_finished(None)
    assert finished_cb.call_args_list == [call(None)]
    assert ctj.output == ()
    assert ctj.is_finished

@patch('upsies.utils.fs.file_tree')
def test_CreateTorrentJob_file_tree(file_tree_mock, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
    )
    assert ctj.info == ''
    file_tree_mock.return_value = 'beautiful file tree'
    ctj.handle_file_tree(('top', ('a', 'b', 'c')))
    assert file_tree_mock.call_args_list == [call(('top', ('a', 'b', 'c')))]
    assert ctj.info == 'beautiful file tree'
