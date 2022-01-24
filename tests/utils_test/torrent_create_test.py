import copy
import datetime
import itertools
import os
import re
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
import torf

from upsies import __project_name__, __version__, errors
from upsies.utils import torrent


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
    mocker.patch('upsies.utils.torrent._get_generated_torrent')
    mocker.patch('upsies.utils.torrent._store_cache_torrent')

    with pytest.raises(errors.TorrentError, match=rf'^{re.escape(exp_error)}$'):
        torrent.create(
            content_path=str(tmp_path / 'content'),
            torrent_path=torrent_path,
            announce=announce,
            source=source,
            init_callback=Mock(),
            progress_callback=Mock(),
            info_callback=Mock(),
            exclude=('a', 'b', 'c'),
        )
    assert torrent._path_exists.call_args_list == []
    assert torrent._read_cache_torrent.call_args_list == []
    assert torrent._get_generated_torrent.call_args_list == []
    assert torrent._store_cache_torrent.call_args_list == []

@pytest.mark.parametrize(
    argnames='overwrite, torrent_exists, cached_torrent, generated_torrent',
    argvalues=(
        pytest.param(False, False, None, Mock(is_ready=True), id='a'),
        pytest.param(False, False, None, Mock(is_ready=False), id='b'),
        pytest.param(False, False, Mock(is_ready=True), None, id='c'),
        pytest.param(False, False, Mock(is_ready=False), None, id='c'),

        pytest.param(False, True, None, Mock(is_ready=True), id='d'),
        pytest.param(False, True, None, Mock(is_ready=False), id='e'),
        pytest.param(False, True, Mock(is_ready=True), None, id='f'),
        pytest.param(False, True, Mock(is_ready=False), None, id='g'),

        pytest.param(True, False, None, Mock(is_ready=True), id=''),
        pytest.param(True, False, None, Mock(is_ready=False), id=''),
        pytest.param(True, False, Mock(is_ready=True), None, id=''),
        pytest.param(True, False, Mock(is_ready=False), None, id=''),

        pytest.param(True, True, None, Mock(is_ready=True), id='h'),
        pytest.param(True, True, None, Mock(is_ready=False), id='i'),
        pytest.param(True, True, Mock(is_ready=True), None, id='j'),
        pytest.param(True, True, Mock(is_ready=False), None, id='k'),
    ),
)
def test_create(overwrite, torrent_exists, cached_torrent, generated_torrent,
                mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    torrent_path = str(tmp_path / 'content.torrent')
    reuse_torrent_path = 'path/to/existing.torrent'
    announce = 'http://foo'
    source = 'ASDF'
    init_callback = Mock()
    progress_callback = Mock()
    info_callback = Mock()
    exclude = ('a', 'b', 'c')

    mocker.patch('upsies.utils.torrent._path_exists', return_value=torrent_exists)
    mocker.patch('upsies.utils.torrent._get_cached_torrent', return_value=cached_torrent)
    mocker.patch('upsies.utils.torrent._get_generated_torrent', return_value=generated_torrent)
    mocker.patch('upsies.utils.torrent._store_cache_torrent')

    if (overwrite or not torrent_exists) and cached_torrent:
        exp_torrent = cached_torrent
    elif (overwrite or not torrent_exists) and generated_torrent:
        exp_torrent = generated_torrent
    else:
        exp_torrent = None

    return_value = torrent.create(
        content_path=content_path,
        announce=announce,
        source=source,
        torrent_path=torrent_path,
        init_callback=init_callback,
        progress_callback=progress_callback,
        info_callback=info_callback,
        overwrite=overwrite,
        exclude=exclude,
        reuse_torrent_path=reuse_torrent_path,
    )
    if exp_torrent and exp_torrent.is_ready:
        assert return_value is torrent_path
    else:
        assert return_value is None

    if not overwrite:
        assert torrent._path_exists.call_args_list == [call(torrent_path)]
    else:
        assert torrent._path_exists.call_args_list == []

    if overwrite or not torrent_exists:
        assert torrent._get_cached_torrent.call_args_list == [call(
            content_path=content_path,
            exclude=exclude,
            metadata={'trackers': (announce,), 'source': source},
            reuse_torrent_path=reuse_torrent_path,
            info_callback=info_callback,
        )]

        if not cached_torrent:
            assert torrent._get_generated_torrent.call_args_list == [call(
                content_path=content_path,
                announce=announce,
                source=source,
                exclude=exclude,
                progress_callback=progress_callback,
                init_callback=init_callback,
            )]
        else:
            assert torrent._get_generated_torrent.call_args_list == []

    if exp_torrent and exp_torrent.is_ready:
        assert torrent._store_cache_torrent.call_args_list == [call(exp_torrent)]
        assert exp_torrent.write.call_args_list == [call(torrent_path, overwrite=True)]

@pytest.mark.parametrize('torrent_provider', ('_get_cached_torrent', '_get_generated_torrent'))
def test_create_handles_TorfError_from_torrent_write(torrent_provider, mocker, tmp_path):
    torrent_path = str(tmp_path / 'content.torrent'),

    exp_torrent = Mock(
        is_ready=True,
        write=Mock(side_effect=torf.TorfError('nope')),
    )
    print('--', exp_torrent.is_ready)
    mocker.patch('upsies.utils.torrent._path_exists', return_value=False)
    mocker.patch('upsies.utils.torrent._store_cache_torrent')
    if torrent_provider == '_get_cached_torrent':
        mocker.patch('upsies.utils.torrent._get_cached_torrent', return_value=exp_torrent)
        mocker.patch('upsies.utils.torrent._get_generated_torrent', return_value=None)
    elif torrent_provider == '_get_generated_torrent':
        mocker.patch('upsies.utils.torrent._get_cached_torrent', return_value=None)
        mocker.patch('upsies.utils.torrent._get_generated_torrent', return_value=exp_torrent)
    else:
        raise RuntimeError(f'Unexpected torrent_provider: {torrent_provider!r}')

    with pytest.raises(errors.TorrentError, match=r'^nope$'):
        torrent.create(
            content_path=str(tmp_path / 'content'),
            torrent_path=torrent_path,
            announce='http://foo',
            source='ASDF',
            init_callback=Mock(),
            progress_callback=Mock(),
            info_callback=Mock(),
            exclude=('a', 'b', 'c'),
        )


def test_get_cached_torrent_from_directory(mocker):
    reuse_torrent_path = 'path/to/cache_directory'
    content_path = 'path/to/content'
    exclude = ('*.jpg',)

    cached_torrent = Mock(name='2.torrent object')

    isdir_mock = mocker.patch('os.path.isdir', return_value=True)
    file_list_mock = mocker.patch('upsies.utils.fs.file_list', return_value=(
        f'{i}.torrent' for i in range(1, 100)
    ))
    read_cache_torrent_mock = mocker.patch('upsies.utils.torrent._read_cache_torrent', side_effect=(
        None,
        cached_torrent,
    ))
    info_callback = Mock(return_value=False)

    t = torrent._get_cached_torrent(
        content_path=content_path,
        exclude=exclude,
        reuse_torrent_path=reuse_torrent_path,
        metadata={'tracker': ('http://localhost:123',), 'source': 'ASDF'},
        info_callback=info_callback,
    )
    assert t is cached_torrent
    assert t.tracker == ('http://localhost:123',)
    assert t.source == 'ASDF'
    assert isdir_mock.call_args_list == [call('path/to/cache_directory')]
    assert file_list_mock.call_args_list == [call('path/to/cache_directory', extensions=('torrent',))]
    assert info_callback.call_args_list == [call('1.torrent'), call('2.torrent')]
    assert read_cache_torrent_mock.call_args_list == [
        call(content_path='path/to/content', cache_torrent_path='1.torrent', exclude=('*.jpg',)),
        call(content_path='path/to/content', cache_torrent_path='2.torrent', exclude=('*.jpg',)),
    ]

def test_get_cached_torrent_from_directory_when_info_callback_cancels(mocker):
    reuse_torrent_path = 'path/to/cache_directory'
    content_path = 'path/to/content'
    exclude = ('*.jpg',)

    isdir_mock = mocker.patch('os.path.isdir', return_value=True)
    file_list_mock = mocker.patch('upsies.utils.fs.file_list', return_value=(
        f'{i}.torrent' for i in range(1, 100)
    ))
    read_cache_torrent_mock = mocker.patch('upsies.utils.torrent._read_cache_torrent', side_effect=(
        '' for i in range(100)
    ))
    info_callback = Mock(side_effect=(False, False, True, False, False))

    t = torrent._get_cached_torrent(
        reuse_torrent_path=reuse_torrent_path,
        content_path=content_path,
        exclude=exclude,
        metadata={'tracker': ('http://localhost:123',), 'source': 'ASDF'},
        info_callback=info_callback,
    )
    assert t is None
    assert isdir_mock.call_args_list == [call('path/to/cache_directory')]
    assert file_list_mock.call_args_list == [call('path/to/cache_directory', extensions=('torrent',))]
    assert info_callback.call_args_list == [call('1.torrent'), call('2.torrent'), call('3.torrent')]
    assert read_cache_torrent_mock.call_args_list == [
        call(content_path='path/to/content', cache_torrent_path='1.torrent', exclude=('*.jpg',)),
        call(content_path='path/to/content', cache_torrent_path='2.torrent', exclude=('*.jpg',)),
    ]

def test_get_cached_torrent_from_file(mocker):
    reuse_torrent_path = 'path/to/cached.torrent'
    content_path = 'path/to/content'
    exclude = ('*.jpg',)

    cached_torrent = Mock(name='torrent object')

    isdir_mock = mocker.patch('os.path.isdir', return_value=False)
    file_list_mock = mocker.patch('upsies.utils.fs.file_list', return_value=())
    read_cache_torrent_mock = mocker.patch('upsies.utils.torrent._read_cache_torrent', return_value=cached_torrent)
    info_callback = Mock(return_value=False)

    t = torrent._get_cached_torrent(
        reuse_torrent_path=reuse_torrent_path,
        content_path=content_path,
        exclude=exclude,
        metadata={'tracker': ('http://localhost:123',), 'source': 'ASDF'},
        info_callback=info_callback,
    )
    assert t is cached_torrent
    assert t.tracker == ('http://localhost:123',)
    assert t.source == 'ASDF'
    assert isdir_mock.call_args_list == [call('path/to/cached.torrent')]
    assert file_list_mock.call_args_list == []
    assert info_callback.call_args_list == []
    assert read_cache_torrent_mock.call_args_list == [
        call(content_path='path/to/content', cache_torrent_path='path/to/cached.torrent', exclude=('*.jpg',)),
    ]

@pytest.mark.parametrize('reuse_torrent_path', (None, ''))
def test_get_cached_torrent_from_generic_torrent(reuse_torrent_path, mocker):
    content_path = 'path/to/content'
    exclude = ('*.jpg',)

    cached_torrent = Mock(name='torrent object')

    isdir_mock = mocker.patch('os.path.isdir', return_value=False)
    file_list_mock = mocker.patch('upsies.utils.fs.file_list', return_value=())
    read_cache_torrent_mock = mocker.patch('upsies.utils.torrent._read_cache_torrent', return_value=cached_torrent)
    info_callback = Mock(return_value=False)

    t = torrent._get_cached_torrent(
        reuse_torrent_path=reuse_torrent_path,
        content_path=content_path,
        exclude=exclude,
        metadata={'tracker': ('http://localhost:123',), 'source': 'ASDF'},
        info_callback=info_callback,
    )
    assert t is cached_torrent
    assert t.tracker == ('http://localhost:123',)
    assert t.source == 'ASDF'
    assert isdir_mock.call_args_list == []
    assert file_list_mock.call_args_list == []
    assert info_callback.call_args_list == []
    assert read_cache_torrent_mock.call_args_list == [
        call(content_path='path/to/content', cache_torrent_path=reuse_torrent_path, exclude=('*.jpg',)),
    ]

@pytest.mark.parametrize('reuse_torrent_path', (None, ''))
def test_get_cached_torrent_when_no_cached_torrent_exists(reuse_torrent_path, mocker):
    content_path = 'path/to/content'
    exclude = ('*.jpg',)

    isdir_mock = mocker.patch('os.path.isdir', return_value=False)
    file_list_mock = mocker.patch('upsies.utils.fs.file_list', return_value=())
    read_cache_torrent_mock = mocker.patch('upsies.utils.torrent._read_cache_torrent', return_value=None)
    info_callback = Mock(return_value=False)

    t = torrent._get_cached_torrent(
        reuse_torrent_path=reuse_torrent_path,
        content_path=content_path,
        exclude=exclude,
        metadata={'tracker': ('http://localhost:123',), 'source': 'ASDF'},
        info_callback=info_callback,
    )
    assert t is None
    assert isdir_mock.call_args_list == []
    assert file_list_mock.call_args_list == []
    assert info_callback.call_args_list == []
    assert read_cache_torrent_mock.call_args_list == [
        call(content_path='path/to/content', cache_torrent_path=reuse_torrent_path, exclude=('*.jpg',)),
    ]


def test_get_generated_torrent(mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    announce = 'http://announce.mock'
    source = 'ASDF',
    created_by = f'{__project_name__} {__version__}'
    time = 'mock time'
    init_callback = Mock(return_value=False)
    progress_callback = Mock()

    Torrent_mock = mocker.patch('torf.Torrent')
    mocker.patch('upsies.utils.torrent._CreateTorrentCallbackWrapper')
    mocker.patch('upsies.utils.torrent._make_file_tree')
    mocker.patch('time.time', return_value=time)

    t = torrent._get_generated_torrent(
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

@pytest.mark.parametrize('init_callback_return_value', (True, 'cancel', 1))
def test_get_generated_torrent_does_not_generate_if_init_callback_returns_truth(init_callback_return_value, mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    announce = 'http://announce.mock'
    source = 'ASDF',
    created_by = f'{__project_name__} {__version__}'
    time = 'mock time'
    init_callback = Mock(return_value=init_callback_return_value)
    progress_callback = Mock()

    Torrent_mock = mocker.patch('torf.Torrent')
    mocker.patch('upsies.utils.torrent._CreateTorrentCallbackWrapper')
    mocker.patch('upsies.utils.torrent._make_file_tree')
    mocker.patch('time.time', return_value=time)

    t = torrent._get_generated_torrent(
        content_path=content_path,
        announce=announce,
        source=source,
        exclude=exclude,
        init_callback=init_callback,
        progress_callback=progress_callback,
    )
    assert t is None
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
    assert Torrent_mock.return_value.generate.call_args_list == []

def test_get_generated_torrent_handles_TorfError_from_Torrent(mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    announce = 'http://announce.mock'
    source = 'ASDF',
    created_by = f'{__project_name__} {__version__}'
    time = 'mock time'
    init_callback = Mock(return_value=False)
    progress_callback = Mock()

    Torrent_mock = mocker.patch('torf.Torrent', side_effect=torf.TorfError('nope'))
    mocker.patch('upsies.utils.torrent._CreateTorrentCallbackWrapper')
    mocker.patch('upsies.utils.torrent._make_file_tree')
    mocker.patch('time.time', return_value=time)

    with pytest.raises(errors.TorrentError, match=r'^nope$'):
        torrent._get_generated_torrent(
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

def test_get_generated_torrent_handles_TorfError_from_Torrent_generate(mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    announce = 'http://announce.mock'
    source = 'ASDF',
    created_by = f'{__project_name__} {__version__}'
    time = 'mock time'
    init_callback = Mock(return_value=False)
    progress_callback = Mock()

    Torrent_mock = mocker.patch('torf.Torrent')
    Torrent_mock.return_value.generate.side_effect = torf.TorfError('nope')
    mocker.patch('upsies.utils.torrent._CreateTorrentCallbackWrapper')
    mocker.patch('upsies.utils.torrent._make_file_tree')
    mocker.patch('time.time', return_value=time)

    with pytest.raises(errors.TorrentError, match=r'^nope$'):
        torrent._get_generated_torrent(
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
    mocker.patch('upsies.utils.torrent._get_generic_torrent_path')
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
    assert torrent._get_generic_torrent_path.call_args_list == [call(
        Torrent_mock.return_value,
        create_directory=True,
    )]
    assert Torrent_mock.return_value.write.call_args_list == [call(
        torrent._get_generic_torrent_path.return_value,
        overwrite=True,
    )]


@pytest.mark.parametrize('torrent_ids_match', (True, False))
@pytest.mark.parametrize('cache_torrent_path', (None, '', 'path/to/existing.torrent'))
def test_read_cache_torrent_from_generated_path(cache_torrent_path, torrent_ids_match, mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    Torrent_mock = mocker.patch('torf.Torrent')
    mocker.patch('upsies.utils.torrent._get_generic_torrent_path', return_value='path/to/cache.torrent')
    mocker.patch('upsies.utils.torrent._copy_torrent_info')
    mocker.patch('time.time', return_value='mock time')

    if torrent_ids_match:
        mocker.patch('upsies.utils.torrent._get_torrent_id', side_effect=('mock id', 'mock id'))
    else:
        mocker.patch('upsies.utils.torrent._get_torrent_id', side_effect=('mock id 1', 'mock id 2'))

    t = torrent._read_cache_torrent(
        content_path=content_path,
        exclude=exclude,
        cache_torrent_path=cache_torrent_path,
    )
    assert Torrent_mock.call_args_list == [call(
        path=content_path,
        exclude_regexs=exclude,
        private=True,
        created_by=f'{__project_name__} {__version__}',
        creation_date='mock time',
    )]

    if cache_torrent_path:
        assert torrent._get_generic_torrent_path.call_args_list == []
        assert Torrent_mock.read.call_args_list == [call(cache_torrent_path)]
    else:
        assert torrent._get_generic_torrent_path.call_args_list == [call(
            Torrent_mock.return_value,
            create_directory=False,
        )]
        assert Torrent_mock.read.call_args_list == [call(torrent._get_generic_torrent_path.return_value)]

    if torrent_ids_match:
        assert torrent._copy_torrent_info.call_args_list == [call(
            Torrent_mock.read.return_value, Torrent_mock.return_value,
        )]
        assert t is Torrent_mock.return_value
    else:
        assert torrent._copy_torrent_info.call_args_list == []
        assert t is None

def test_read_cache_torrent_handles_TorfError_from_Torrent(mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    Torrent_mock = mocker.patch('torf.Torrent', side_effect=torf.TorfError('nope'))
    mocker.patch('upsies.utils.torrent._get_generic_torrent_path')
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
    assert torrent._get_generic_torrent_path.call_args_list == []
    assert Torrent_mock.read.call_args_list == []
    assert torrent._copy_torrent_info.call_args_list == []

def test_read_cache_torrent_handles_TorfError_from_Torrent_read(mocker, tmp_path):
    content_path = str(tmp_path / 'content')
    exclude = ('foo', 'bar', 'baz')
    Torrent_mock = mocker.patch('torf.Torrent', Mock(read=Mock(side_effect=torf.TorfError('nope'))))
    mocker.patch('upsies.utils.torrent._get_generic_torrent_path')
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
    assert torrent._get_generic_torrent_path.call_args_list == [call(
        Torrent_mock.return_value,
        create_directory=False,
    )]
    assert Torrent_mock.read.call_args_list == [call(
        torrent._get_generic_torrent_path.return_value
    )]
    assert torrent._copy_torrent_info.call_args_list == []


@pytest.mark.parametrize(
    argnames='generic_torrents_dirpath, create_directory',
    argvalues=(
        ('path/to/generic_torrents', False),
        ('path/to/generic_torrents', True),
    ),
    ids=lambda v: str(v),
)
def test_get_generic_torrent_path(generic_torrents_dirpath, create_directory, mocker, tmp_path):
    generic_torrents_dirpath = str(tmp_path / generic_torrents_dirpath)
    mocker.patch('upsies.constants.GENERIC_TORRENTS_DIRPATH', generic_torrents_dirpath)
    mock_mkdir = mocker.patch('upsies.utils.fs.mkdir')
    mock_get_torrent_id = mocker.patch('upsies.utils.torrent._get_torrent_id', return_value='D34DB33F')

    cache_torrent = SimpleNamespace(name='The Torrent')
    exp_cache_torrent_path = os.path.join(
        generic_torrents_dirpath,
        f'{cache_torrent.name}.{mock_get_torrent_id.return_value}.torrent',
    )
    cache_torrent_path = torrent._get_generic_torrent_path(cache_torrent, create_directory=create_directory)
    assert cache_torrent_path == cache_torrent_path
    if create_directory:
        assert mock_mkdir.call_args_list == [call(os.path.dirname(exp_cache_torrent_path))]
    else:
        assert mock_mkdir.call_args_list == []
    assert mock_get_torrent_id.call_args_list == [call(cache_torrent)]

def test_get_generic_torrent_path_handles_ContentError_from_mkdir(mocker, tmp_path):
    generic_torrents_dirpath = str(tmp_path / 'generic_torrents')
    mocker.patch('upsies.constants.GENERIC_TORRENTS_DIRPATH', generic_torrents_dirpath)
    mocker.patch('upsies.utils.fs.mkdir', side_effect=errors.ContentError('nope'))
    mocker.patch('upsies.utils.torrent._get_torrent_id', return_value='D34DB33F')
    cache_torrent = Mock()
    with pytest.raises(errors.TorrentError, match=rf'^{generic_torrents_dirpath}: nope$'):
        torrent._get_generic_torrent_path(cache_torrent, create_directory=True)


def test_get_torrent_id(mocker):
    class MockFile(str):
        def __new__(cls, string, size):
            self = super().__new__(cls, string)
            self.size = size
            return self

    mock_torrent = SimpleNamespace(
        name='Foo',
        files=(MockFile('a', size=123), MockFile('b', size=456)),
    )
    mock_semantic_hash = mocker.patch('upsies.utils.semantic_hash', return_value='D34DB33F')

    cache_id = torrent._get_torrent_id(mock_torrent)
    assert cache_id == 'D34DB33F'
    assert mock_semantic_hash.call_args_list == [call({
        'name': 'Foo',
        'files': (('a', 123), ('b', 456)),
    })]


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
    seconds_started = 100
    seconds_increment = 3
    mocker.patch('time.time', side_effect=itertools.count(
        start=seconds_started,
        step=seconds_increment,
    ))

    progress_cb = Mock()
    cbw = torrent._CreateTorrentCallbackWrapper(progress_cb)
    pieces_total = 12
    for pieces_done in range(0, pieces_total + 1):
        return_value = cbw(Mock(piece_size=450, size=5000), 'current/file', pieces_done, pieces_total)
        assert return_value is progress_cb.return_value
        status = progress_cb.call_args[0][0]

        assert status.filepath == 'current/file'
        assert status.percent_done == max(0, min(100, pieces_done / pieces_total * 100))
        assert status.piece_size == 450
        assert status.pieces_done == pieces_done
        assert status.pieces_total == pieces_total
        assert status.seconds_elapsed == datetime.timedelta(seconds=seconds_increment * (pieces_done + 1))
        assert status.time_started == datetime.datetime.fromtimestamp(seconds_started)
        assert status.total_size == 5000

        # TODO: If you're a Python wizard, feel free to add tests for these
        #       CreateTorrentProgress attributes: bytes_per_second,
        #       seconds_remaining, seconds_total, time_finished
