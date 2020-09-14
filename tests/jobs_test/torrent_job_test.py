import asyncio
import multiprocessing
import os
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs._common import DaemonProcess
from upsies.jobs.torrent import CreateTorrentJob, _torrent_process
from upsies.tools import client


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

def make_MockClient():
    class MockClient(client.ClientApiBase):
        name = 'mocksy'
        add_torrent = AsyncMock()

        def __repr__(self):
            return '<MockClient instance>'

    return MockClient()


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
def test_CreateTorrentJob_initialize_without_handling_torrent(torrent_process_mock, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='ASDF',
        source='AsdF',
        exclude_regexs=('a', 'b'),
    )
    assert not ctj.is_finished
    assert ctj.info == ''
    assert torrent_process_mock.call_args_list == []
    assert ctj._torrent_path == f'{tmp_path / "foo"}.asdf.torrent'
    assert ctj._destination_path is None

@patch('upsies.jobs.torrent._torrent_process')
def test_CreateTorrentJob_initialize_with_add_to_argument(torrent_process_mock, tmp_path):
    client_mock = make_MockClient()
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
        add_to=client_mock,
    )
    assert not ctj.is_finished
    assert ctj.info == ''
    assert torrent_process_mock.call_args_list == []
    assert client_mock.add_torrent.call_args_list == []
    assert ctj._destination_path is None

@patch('upsies.jobs.torrent._torrent_process')
def test_CreateTorrentJob_initialize_with_copy_to_argument(torrent_process_mock, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
        copy_to='destination/path',
    )
    assert not ctj.is_finished
    assert ctj.info == ''
    assert torrent_process_mock.call_args_list == []
    assert ctj._destination_path == 'destination/path'
    assert ctj._client is None


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
            'overwrite'      : False,
            'announce_url'   : 'http://foo.bar',
            'source'         : 'AsdF',
            'exclude_regexs' : ('a', 'b'),
        },
        init_callback=ctj.handle_file_tree,
        info_callback=ctj.handle_progress_update,
        error_callback=ctj.handle_error,
        finished_callback=ctj.handle_torrent_created,
    )]
    assert process_mock.return_value.start.call_args_list == [call()]


@patch('upsies.jobs._common.DaemonProcess')
def test_CreateTorrentJob_finish_with_torrent_created(process_mock, tmp_path):
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
    ctj.execute()
    assert not ctj.is_finished
    assert finished_cb.call_args_list == []
    ctj.send('mock/output.torrent')
    ctj.finish()
    assert process_mock.return_value.stop.call_args_list == [call()]
    assert ctj.is_finished
    assert finished_cb.call_args_list == [call('mock/output.torrent')]

@patch('upsies.jobs._common.DaemonProcess')
def test_CreateTorrentJob_finish_without_torrent_created(process_mock, tmp_path):
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
    ctj.execute()
    assert not ctj.is_finished
    assert finished_cb.call_args_list == []
    ctj.finish()
    assert process_mock.return_value.stop.call_args_list == [call()]
    assert ctj.is_finished
    assert finished_cb.call_args_list == [call(None)]


@patch('upsies.jobs._common.DaemonProcess', return_value=Mock(join=AsyncMock()))
def test_CreateTorrentJob_wait_without_handling_torrent(process_mock, tmp_path):
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

@patch('upsies.jobs._common.DaemonProcess', return_value=Mock(join=AsyncMock()))
def test_CreateTorrentJob_wait_with_handling_torrent(process_mock, tmp_path):
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
    ctj._handle_torrent_task = AsyncMock()
    assert ctj._handle_torrent_task.call_args_list == []
    assert not ctj.is_finished
    asyncio.get_event_loop().call_soon(ctj.finish)
    asyncio.get_event_loop().run_until_complete(ctj.wait())
    assert process_mock.return_value.join.call_args_list == [call()]
    assert ctj.is_finished
    assert ctj._handle_torrent_task.call_args_list == [call()]


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


def test_CreateTorrentJob_handle_torrent_created_successfully_without_torrent_handling(tmp_path):
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
    add_torrent_mock = AsyncMock()
    copy_torrent_mock = AsyncMock()
    with patch.multiple(ctj, _add_torrent=add_torrent_mock, _copy_torrent=copy_torrent_mock):
        assert add_torrent_mock.call_args_list == []
        assert copy_torrent_mock.call_args_list == []
        ctj.handle_torrent_created('path/to/torrent')
    assert add_torrent_mock.call_args_list == []
    assert copy_torrent_mock.call_args_list == []
    assert finished_cb.call_args_list == [call('path/to/torrent')]
    assert ctj.output == ('path/to/torrent',)
    assert ctj.is_finished

def test_CreateTorrentJob_handle_torrent_created_successfully_with_add_to_argument(tmp_path):
    client_mock = make_MockClient()
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
        add_to=client_mock,
    )
    finished_cb = Mock()
    ctj.on_finished(finished_cb)
    add_torrent_mock = AsyncMock()
    copy_torrent_mock = AsyncMock()
    with patch.multiple(ctj, _add_torrent=add_torrent_mock, _copy_torrent=copy_torrent_mock):
        assert add_torrent_mock.call_args_list == []
        assert copy_torrent_mock.call_args_list == []
        ctj.handle_torrent_created('path/to/torrent')
        assert not ctj.is_finished
        asyncio.get_event_loop().run_until_complete(ctj.wait())

    assert add_torrent_mock.call_args_list == [call(
        torrent_path='path/to/torrent',
        download_path=os.path.dirname('path/to/foo'),
        client=client_mock,
    )]
    assert copy_torrent_mock.call_args_list == []
    assert ctj.is_finished

def test_CreateTorrentJob_handle_torrent_created_successfully_with_copy_to_argument(tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
        copy_to='destination/path',
    )
    finished_cb = Mock()
    ctj.on_finished(finished_cb)
    add_torrent_mock = AsyncMock()
    copy_torrent_mock = AsyncMock()
    with patch.multiple(ctj, _add_torrent=add_torrent_mock, _copy_torrent=copy_torrent_mock):
        assert add_torrent_mock.call_args_list == []
        assert copy_torrent_mock.call_args_list == []
        ctj.handle_torrent_created('path/to/torrent')
        assert not ctj.is_finished
        asyncio.get_event_loop().run_until_complete(ctj.wait())

    assert add_torrent_mock.call_args_list == []
    assert copy_torrent_mock.call_args_list == [call(
        torrent_path='path/to/torrent',
        destination_path='destination/path',
    )]
    assert ctj.is_finished


def test_CreateTorrentJob_handle_torrent_created_unsuccessfully_without_torrent_handling(tmp_path):
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
    add_torrent_mock = AsyncMock()
    copy_torrent_mock = AsyncMock()
    with patch.multiple(ctj, _add_torrent=add_torrent_mock, _copy_torrent=copy_torrent_mock):
        assert add_torrent_mock.call_args_list == []
        assert copy_torrent_mock.call_args_list == []
        ctj.handle_torrent_created(None)
    assert add_torrent_mock.call_args_list == []
    assert copy_torrent_mock.call_args_list == []
    assert finished_cb.call_args_list == [call(None)]
    assert ctj.output == ()
    assert ctj.is_finished

def test_CreateTorrentJob_handle_torrent_created_unsuccessfully_with_add_to_argument(tmp_path):
    client_mock = make_MockClient()
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
        add_to=client_mock,
    )
    finished_cb = Mock()
    ctj.on_finished(finished_cb)
    add_torrent_mock = AsyncMock()
    copy_torrent_mock = AsyncMock()
    with patch.multiple(ctj, _add_torrent=add_torrent_mock, _copy_torrent=copy_torrent_mock):
        assert add_torrent_mock.call_args_list == []
        assert copy_torrent_mock.call_args_list == []
        ctj.handle_torrent_created(None)
    assert add_torrent_mock.call_args_list == []
    assert copy_torrent_mock.call_args_list == []
    assert finished_cb.call_args_list == [call(None)]
    assert ctj.output == ()
    assert ctj.is_finished

def test_CreateTorrentJob_handle_torrent_created_unsuccessfully_with_copy_to_argument(tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
        copy_to='destination/path',
    )
    finished_cb = Mock()
    ctj.on_finished(finished_cb)
    add_torrent_mock = AsyncMock()
    copy_torrent_mock = AsyncMock()
    with patch.multiple(ctj, _add_torrent=add_torrent_mock, _copy_torrent=copy_torrent_mock):
        assert add_torrent_mock.call_args_list == []
        assert copy_torrent_mock.call_args_list == []
        ctj.handle_torrent_created(None)
    assert add_torrent_mock.call_args_list == []
    assert copy_torrent_mock.call_args_list == []
    assert finished_cb.call_args_list == [call(None)]
    assert ctj.output == ()
    assert ctj.is_finished


@pytest.mark.parametrize(
    argnames=('kwargs', 'exp_attrs'),
    argvalues=(
        ({'add_to': None, 'copy_to': None}, {'is_adding_torrent': False, 'is_copying_torrent': False}),
        ({'add_to': make_MockClient(), 'copy_to': None}, {'is_adding_torrent': True, 'is_copying_torrent': False}),
        ({'add_to': None, 'copy_to': 'p/a/t/h'}, {'is_adding_torrent': False, 'is_copying_torrent': True}),
        ({'add_to': make_MockClient(), 'copy_to': 'p/a/t/h'}, {'is_adding_torrent': True, 'is_copying_torrent': True}),
    ),
    ids=lambda val: ', '.join(f'{k}={v!r}' for k,v in val.items()),
)
def test_CreateTorrentJob_is_adding_torrent_property(kwargs, exp_attrs, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
        **kwargs,
    )
    for k, v in exp_attrs.items():
        assert getattr(ctj, k) is v


def test_CreateTorrentJob_add_torrent_succeeds(tmp_path):
    client_mock = make_MockClient()
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
        add_to=client_mock,
    )
    asyncio.get_event_loop().run_until_complete(ctj._add_torrent(
        torrent_path='path/to/torrent',
        download_path='path/to/content',
        client=client_mock,
    ))
    assert client_mock.add_torrent.call_args_list == [call(
        torrent_path='path/to/torrent',
        download_path='path/to/content',
    )]
    assert ctj.output == ('path/to/torrent',)

def test_CreateTorrentJob_add_torrent_fails(tmp_path):
    client_mock = make_MockClient()
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
        add_to=client_mock,
    )
    client_mock.add_torrent.side_effect = errors.RequestError('Connection refused')
    asyncio.get_event_loop().run_until_complete(ctj._add_torrent(
        torrent_path='path/to/torrent',
        download_path='path/to/content',
        client=client_mock,
    ))
    assert client_mock.add_torrent.call_args_list == [call(
        torrent_path='path/to/torrent',
        download_path='path/to/content',
    )]
    assert ctj.output == ('path/to/torrent',)
    assert ctj.errors == (f'Failed to add foo.asdf.torrent to {client_mock.name}: Connection refused',)


@patch('shutil.copy2')
def test_CreateTorrentJob_copy_torrent_succeeds(copy2_mock, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
        copy_to='destination/path',
    )
    copy2_mock.return_value = 'destination/path/torrent'
    asyncio.get_event_loop().run_until_complete(ctj._copy_torrent(
        torrent_path='path/to/torrent',
        destination_path='destination/path',
    ))
    assert copy2_mock.call_args_list == [call('path/to/torrent', 'destination/path')]
    assert ctj.output == ('destination/path/torrent',)

@patch('shutil.copy2')
def test_CreateTorrentJob_copy_torrent_fails(copy2_mock, tmp_path):
    ctj = CreateTorrentJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='path/to/foo',
        announce_url='http://foo.bar',
        trackername='asdf',
        source='AsdF',
        exclude_regexs=('a', 'b'),
        copy_to='destination/path',
    )
    copy2_mock.side_effect = OSError('Nooo!')
    asyncio.get_event_loop().run_until_complete(ctj._copy_torrent(
        torrent_path='path/to/torrent',
        destination_path='destination/path',
    ))
    assert copy2_mock.call_args_list == [call('path/to/torrent', 'destination/path')]
    assert ctj.output == ('path/to/torrent',)
    assert ctj.errors == ('Failed to copy torrent to destination/path: Nooo!',)
