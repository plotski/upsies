import copy
import os
import re
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
import torf

from upsies import __project_name__, __version__, errors
from upsies.utils import torrent


@pytest.mark.parametrize(
    argnames='torrent_path_exists, overwrite, torrent_is_ready, exp_torrent_created',
    argvalues=(
        (True, True, True, True),
        (True, True, False, True),
        (True, False, True, False),
        (True, False, False, False),
        (False, True, True, True),
        (False, True, False, True),
        (False, False, True, True),
        (False, False, False, True),
    ),
)
@pytest.mark.parametrize('torrent_from_cache', (False, True))
def test_create(torrent_from_cache, torrent_path_exists, overwrite, torrent_is_ready, exp_torrent_created, mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    torrent_path = str(tmp_path / 'content.torrent')
    announce = 'http://foo'
    source = 'ASDF'
    init_callback = Mock()
    progress_callback = Mock()
    exclude = ('a', 'b', 'c')

    mocker.patch('upsies.utils.torrent._path_exists', return_value=torrent_path_exists)
    mocker.patch('upsies.utils.torrent._read_cache_torrent', return_value=Mock() if torrent_from_cache else None)
    mocker.patch('upsies.utils.torrent._generate_torrent', return_value=Mock(is_ready=torrent_is_ready))
    mocker.patch('upsies.utils.torrent._store_cache_torrent')
    exp_torrent = torrent._read_cache_torrent.return_value or torrent._generate_torrent.return_value

    t_path = torrent.create(
        content_path=content_path,
        announce=announce,
        source=source,
        torrent_path=torrent_path,
        init_callback=init_callback,
        progress_callback=progress_callback,
        overwrite=overwrite,
        exclude=exclude,
    )
    assert t_path == torrent_path
    if not overwrite:
        assert torrent._path_exists.call_args_list == [call(torrent_path)]
    else:
        assert torrent._path_exists.call_args_list == []

    if exp_torrent_created:
        assert torrent._read_cache_torrent.call_args_list == [call(content_path=content_path, exclude=exclude)]
        if torrent_from_cache:
            assert exp_torrent.trackers == ((announce,))
            assert exp_torrent.source == source
        else:
            assert torrent._generate_torrent.call_args_list == [call(
                content_path=content_path,
                announce=announce,
                source=source,
                exclude=exclude,
                progress_callback=progress_callback,
                init_callback=init_callback,
            )]
            if torrent_is_ready:
                assert torrent._store_cache_torrent.call_args_list == [call(exp_torrent)]
            else:
                assert torrent._store_cache_torrent.call_args_list == []

        assert exp_torrent.write.call_args_list == [call(torrent_path, overwrite=True)]

    else:
        assert torrent._read_cache_torrent.call_args_list == []
        assert torrent._generate_torrent.call_args_list == []
        assert torrent._store_cache_torrent.call_args_list == []
        assert exp_torrent.write.call_args_list == []


@pytest.mark.parametrize(
    argnames='announce, source, exp_error',
    argvalues=(
        ('http://foo', '', 'Source is empty'),
        ('', 'ASDF', 'Announce URL is empty'),
        ('', '', 'Announce URL is empty'),
    ),
)
def test_create_validates_arguments(announce, source, exp_error, mocker, tmp_path):
    torrent_path = str(tmp_path / 'content.torrent'),

    mocker.patch('upsies.utils.torrent._path_exists', return_value=False)
    mocker.patch('upsies.utils.torrent._read_cache_torrent')
    mocker.patch('upsies.utils.torrent._generate_torrent')
    mocker.patch('upsies.utils.torrent._store_cache_torrent')

    with pytest.raises(errors.TorrentError, match=rf'^{re.escape(exp_error)}$'):
        torrent.create(
            content_path=str(tmp_path / 'content'),
            torrent_path=torrent_path,
            announce=announce,
            source=source,
            init_callback=Mock(),
            progress_callback=Mock(),
            exclude=('a', 'b', 'c'),
        )
    assert torrent._path_exists.call_args_list == []
    assert torrent._read_cache_torrent.call_args_list == []
    assert torrent._generate_torrent.call_args_list == []
    assert torrent._store_cache_torrent.call_args_list == []

def test_create_handles_TorfError_from_torrent_write(mocker, tmp_path):
    torrent_path = str(tmp_path / 'content.torrent'),

    mocker.patch('upsies.utils.torrent._path_exists', return_value=False)
    mocker.patch('upsies.utils.torrent._read_cache_torrent')
    mocker.patch('upsies.utils.torrent._generate_torrent')
    mocker.patch('upsies.utils.torrent._store_cache_torrent')
    torrent._read_cache_torrent.return_value.write.side_effect = torf.TorfError('nope')

    print('cached_torrent:', torrent._read_cache_torrent.return_value)
    print('created_torrent:', torrent._generate_torrent.return_value)

    with pytest.raises(errors.TorrentError, match=r'^nope$'):
        torrent.create(
            content_path=str(tmp_path / 'content'),
            torrent_path=torrent_path,
            announce='http://foo',
            source='ASDF',
            init_callback=Mock(),
            progress_callback=Mock(),
            exclude=('a', 'b', 'c'),
        )


def test_generate_torrent(mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    announce = 'http://announce.mock'
    source = 'ASDF',
    created_by = f'{__project_name__} {__version__}'
    time = 'mock time'
    init_callback = Mock()
    progress_callback = Mock()

    Torrent_mock = mocker.patch('torf.Torrent')
    mocker.patch('upsies.utils.torrent._CreateTorrentCallbackWrapper')
    mocker.patch('upsies.utils.torrent._make_file_tree')
    mocker.patch('time.time', return_value=time)

    t = torrent._generate_torrent(
        content_path=content_path,
        announce=announce,
        source=source,
        exclude=exclude,
        init_callback=init_callback,
        progress_callback=progress_callback,
    )
    assert t == Torrent_mock.return_value
    assert Torrent_mock.call_args_list == [call(
        path=content_path,
        exclude_regexs=exclude,
        trackers=((announce,),),
        private=True,
        source=source,
        created_by=created_by,
        creation_date=time,
    )]
    assert torrent._CreateTorrentCallbackWrapper.call_args_list == [call(progress_callback)]
    assert torrent._make_file_tree.call_args_list == [call(Torrent_mock.return_value.filetree)]
    assert init_callback.call_args_list == [call(torrent._make_file_tree.return_value)]
    assert Torrent_mock.return_value.generate.call_args_list == [call(
        callback=torrent._CreateTorrentCallbackWrapper.return_value,
        interval=1.0,
    )]

def test_generate_torrent_handles_TorfError_from_Torrent(mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    announce = 'http://announce.mock'
    source = 'ASDF',
    created_by = f'{__project_name__} {__version__}'
    time = 'mock time'
    init_callback = Mock()
    progress_callback = Mock()

    Torrent_mock = mocker.patch('torf.Torrent', side_effect=torf.TorfError('nope'))
    mocker.patch('upsies.utils.torrent._CreateTorrentCallbackWrapper')
    mocker.patch('upsies.utils.torrent._make_file_tree')
    mocker.patch('time.time', return_value=time)

    with pytest.raises(errors.TorrentError, match=r'^nope$'):
        torrent._generate_torrent(
            content_path=content_path,
            announce=announce,
            source=source,
            exclude=exclude,
            init_callback=init_callback,
            progress_callback=progress_callback,
        )
    assert Torrent_mock.call_args_list == [call(
        path=content_path,
        exclude_regexs=exclude,
        trackers=((announce,),),
        private=True,
        source=source,
        created_by=created_by,
        creation_date=time,
    )]
    assert torrent._CreateTorrentCallbackWrapper.call_args_list == [call(progress_callback)]
    assert torrent._make_file_tree.call_args_list == []
    assert init_callback.call_args_list == []
    assert Torrent_mock.return_value.generate.call_args_list == []

def test_generate_torrent_handles_TorfError_from_Torrent_generate(mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    announce = 'http://announce.mock'
    source = 'ASDF',
    created_by = f'{__project_name__} {__version__}'
    time = 'mock time'
    init_callback = Mock()
    progress_callback = Mock()

    Torrent_mock = mocker.patch('torf.Torrent')
    Torrent_mock.return_value.generate.side_effect = torf.TorfError('nope')
    mocker.patch('upsies.utils.torrent._CreateTorrentCallbackWrapper')
    mocker.patch('upsies.utils.torrent._make_file_tree')
    mocker.patch('time.time', return_value=time)

    with pytest.raises(errors.TorrentError, match=r'^nope$'):
        torrent._generate_torrent(
            content_path=content_path,
            announce=announce,
            source=source,
            exclude=exclude,
            init_callback=init_callback,
            progress_callback=progress_callback,
        )
    assert Torrent_mock.call_args_list == [call(
        path=content_path,
        exclude_regexs=exclude,
        trackers=((announce,),),
        private=True,
        source=source,
        created_by=created_by,
        creation_date=time,
    )]
    assert torrent._CreateTorrentCallbackWrapper.call_args_list == [call(progress_callback)]
    assert torrent._make_file_tree.call_args_list == [call(Torrent_mock.return_value.filetree)]
    assert init_callback.call_args_list == [call(torrent._make_file_tree.return_value)]
    assert Torrent_mock.return_value.generate.call_args_list == [call(
        callback=torrent._CreateTorrentCallbackWrapper.return_value,
        interval=1.0,
    )]


def test_store_cache_torrent(mocker, tmp_path):
    Torrent_mock = mocker.patch('torf.Torrent')
    mocker.patch('upsies.utils.torrent._get_cache_torrent_path')
    mocker.patch('upsies.utils.torrent._copy_torrent_info')
    mocker.patch('time.time', return_value='mock time')
    mock_torrent = Mock()
    torrent._store_cache_torrent(mock_torrent)
    assert Torrent_mock.call_args_list == [call(
        private=True,
        created_by=f'{__project_name__} {__version__}',
        creation_date='mock time',
        comment='This torrent is used to cache previously hashed pieces.',
    )]
    assert torrent._copy_torrent_info.call_args_list == [call(
        mock_torrent, Torrent_mock.return_value,
    )]
    assert torrent._get_cache_torrent_path.call_args_list == [call(
        Torrent_mock.return_value,
        create_directory=True,
    )]
    assert Torrent_mock.return_value.write.call_args_list == [call(
        torrent._get_cache_torrent_path.return_value,
        overwrite=True,
    )]


def test_read_cache_torrent_returns_Torrent_instance(mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    Torrent_mock = mocker.patch('torf.Torrent')
    mocker.patch('upsies.utils.torrent._get_cache_torrent_path')
    mocker.patch('upsies.utils.torrent._copy_torrent_info')
    mocker.patch('time.time', return_value='mock time')
    t = torrent._read_cache_torrent(content_path, exclude=exclude)
    assert t is Torrent_mock.return_value
    assert Torrent_mock.call_args_list == [call(
        path=content_path,
        exclude_regexs=exclude,
        private=True,
        created_by=f'{__project_name__} {__version__}',
        creation_date='mock time',
    )]
    assert torrent._get_cache_torrent_path.call_args_list == [call(
        Torrent_mock.return_value,
        create_directory=False,
    )]
    assert Torrent_mock.read.call_args_list == [call(
        torrent._get_cache_torrent_path.return_value
    )]
    assert torrent._copy_torrent_info.call_args_list == [call(
        Torrent_mock.read.return_value, Torrent_mock.return_value,
    )]

def test_read_cache_torrent_handles_TorfError_from_Torrent(mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    Torrent_mock = mocker.patch('torf.Torrent', side_effect=torf.TorfError('nope'))
    mocker.patch('upsies.utils.torrent._get_cache_torrent_path')
    mocker.patch('upsies.utils.torrent._copy_torrent_info')
    mocker.patch('time.time', return_value='mock time')
    t = torrent._read_cache_torrent(content_path, exclude=exclude)
    assert t is None
    assert Torrent_mock.call_args_list == [call(
        path=content_path,
        exclude_regexs=exclude,
        private=True,
        created_by=f'{__project_name__} {__version__}',
        creation_date='mock time',
    )]
    assert torrent._get_cache_torrent_path.call_args_list == []
    assert Torrent_mock.read.call_args_list == []
    assert torrent._copy_torrent_info.call_args_list == []

def test_read_cache_torrent_handles_TorfError_from_Torrent_read(mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    Torrent_mock = mocker.patch('torf.Torrent', Mock(read=Mock(side_effect=torf.TorfError('nope'))))
    mocker.patch('upsies.utils.torrent._get_cache_torrent_path')
    mocker.patch('upsies.utils.torrent._copy_torrent_info')
    mocker.patch('time.time', return_value='mock time')
    t = torrent._read_cache_torrent(content_path, exclude=exclude)
    assert t is None
    assert Torrent_mock.call_args_list == [call(
        path=content_path,
        exclude_regexs=exclude,
        private=True,
        created_by=f'{__project_name__} {__version__}',
        creation_date='mock time',
    )]
    assert torrent._get_cache_torrent_path.call_args_list == [call(
        Torrent_mock.return_value,
        create_directory=False,
    )]
    assert Torrent_mock.read.call_args_list == [call(
        torrent._get_cache_torrent_path.return_value
    )]
    assert torrent._copy_torrent_info.call_args_list == []


class MockFile(str):
    def __new__(cls, string, size):
        self = super().__new__(cls, string)
        self.size = size
        return self

@pytest.mark.parametrize(
    argnames='cache_torrent, cache_dirpath, create_directory',
    argvalues=(
        (
            SimpleNamespace(name='Foo', piece_size=123, files=(MockFile('a', size=123), MockFile('b', size=456))),
            'path/to/cache',
            False,
        ),
        (
            SimpleNamespace(name='Foo', piece_size=123, files=(MockFile('a', size=123), MockFile('b', size=456))),
            'path/to/cache',
            True,
        ),
    ),
    ids=lambda v: str(v),
)
def test_get_cache_torrent_path(cache_torrent, cache_dirpath, create_directory, mocker, tmp_path):
    cache_dirpath = str(tmp_path / cache_dirpath)
    mocker.patch('upsies.constants.CACHE_DIRPATH', cache_dirpath)
    mock_mkdir = mocker.patch('upsies.utils.fs.mkdir')
    mock_semantic_hash = mocker.patch('upsies.utils.semantic_hash', return_value='D34DB33F')

    exp_cache_torrent_path = os.path.join(
        cache_dirpath,
        'generic_torrents',
        f'{cache_torrent.name}.{mock_semantic_hash.return_value}.torrent',
    )
    cache_torrent_path = torrent._get_cache_torrent_path(cache_torrent, create_directory=create_directory)
    assert cache_torrent_path == cache_torrent_path
    if create_directory:
        assert mock_mkdir.call_args_list == [call(os.path.dirname(exp_cache_torrent_path))]
    else:
        assert mock_mkdir.call_args_list == []
    assert mock_semantic_hash.call_args_list == [call(
        {
            'files': [(str(f), f.size) for f in cache_torrent.files],
            'piece_size': cache_torrent.piece_size,
        },
    )]

def test_get_cache_torrent_path_handles_ContentError_from_mkdir(mocker, tmp_path):
    cache_torrent = Mock()
    mocker.patch('upsies.constants.CACHE_DIRPATH', str(tmp_path / 'cache'))
    mocker.patch('upsies.utils.fs.mkdir', side_effect=errors.ContentError('nope'))
    mocker.patch('upsies.utils.semantic_hash', return_value='D34DB33F')
    with pytest.raises(errors.TorrentError, match=rf'^{tmp_path / "cache" / "generic_torrents"}: nope$'):
        torrent._get_cache_torrent_path(cache_torrent, create_directory=True)


@pytest.mark.parametrize(
    argnames='info_a, info_b, exp_info_b',
    argvalues=(
        (
            {'pieces': 'pieces a', 'piece length': 'piece length a', 'name': 'name a', 'length': 'length a', 'foo': 'bar'},
            {},
            {'pieces': 'pieces a', 'piece length': 'piece length a', 'name': 'name a', 'length': 'length a'},
        ),
        (
            {'pieces': 'pieces a', 'piece length': 'piece length a', 'name': 'name a', 'files': 'files a', 'foo': 'bar'},
            {},
            {'pieces': 'pieces a', 'piece length': 'piece length a', 'name': 'name a', 'files': 'files a'},
        ),
        (
            {'pieces': 'pieces a', 'piece length': 'piece length a', 'name': 'name a', 'length': 'length a', 'foo': 'bar'},
            {'pieces': 'pieces b', 'piece length': 'piece length b', 'name': 'name b', 'length': 'length b', 'foo': 'baz'},
            {'pieces': 'pieces a', 'piece length': 'piece length a', 'name': 'name a', 'length': 'length a', 'foo': 'baz'},
        ),
        (
            {'pieces': 'pieces a', 'piece length': 'piece length a', 'name': 'name a', 'files': 'files a', 'foo': 'bar'},
            {'pieces': 'pieces b', 'piece length': 'piece length b', 'name': 'name b', 'files': 'files b', 'foo': 'baz'},
            {'pieces': 'pieces a', 'piece length': 'piece length a', 'name': 'name a', 'files': 'files a', 'foo': 'baz'},
        ),
    ),
    ids=lambda v: str(v),
)
def test_copy_torrent_info(info_a, info_b, exp_info_b):
    info_a_orig = copy.deepcopy(info_a)
    a, b = Mock(metainfo={'info': info_a}), Mock(metainfo={'info': info_b})
    torrent._copy_torrent_info(a, b)
    assert info_b == exp_info_b
    assert info_a == info_a_orig


def test_make_file_tree():
    class File(str):
        def __new__(cls, string, size):
            self = super().__new__(cls, string)
            self.size = size
            return self

    filetree = {
        'Top': {
            'a': File('a', 123),
            'b': {
                'c': File('c', 456),
                'd': File('d', 789),
            }
        }
    }
    assert torrent._make_file_tree(filetree) == (
        (('Top', (
            ('a', 123),
            ('b', (
                ('c', 456),
                ('d', 789),
            ))
        ))),
    )


def test_CreateTorrentCallbackWrapper(mocker):
    progress_cb = Mock()
    cbw = torrent._CreateTorrentCallbackWrapper(progress_cb)
    pieces_total = 12
    for pieces_done in range(0, pieces_total + 1):
        return_value = cbw(Mock(piece_size=450, size=5000), 'current/file', pieces_done, pieces_total)
        assert return_value is progress_cb.return_value
        status = progress_cb.call_args[0][0]
        assert status.percent_done == max(0, min(100, pieces_done / pieces_total * 100))
        assert status.piece_size == 450
        assert status.total_size == 5000
        assert status.pieces_done == pieces_done
        assert status.pieces_total == pieces_total
        assert status.filepath == 'current/file'

        # TODO: If you're a Python wizard, feel free to add tests for these
        #       CreateTorrentStatus attributes: seconds_elapsed,
        #       seconds_remaining, seconds_total, time_finished, time_started
