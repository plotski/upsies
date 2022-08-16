import copy
import datetime
import errno
import os
import re
from unittest.mock import Mock, call, patch

import pytest
import torf

from upsies import __project_name__, __version__, errors
from upsies.utils import torrent, types


@pytest.mark.parametrize(
    argnames='announce, source, exp_error',
    argvalues=(
        ('http://foo', '', 'Source is empty'),
        ('', 'ASDF', 'Announce URL is empty'),
        ('', '', 'Announce URL is empty'),
    ),
)
def test_create_validates_arguments(announce, source, exp_error, mocker):
    mocker.patch('upsies.utils.torrent._get_torrent')
    mocker.patch('upsies.utils.torrent._make_file_tree')
    mocker.patch('upsies.utils.torrent._find_hashes')
    mocker.patch('upsies.utils.torrent._generate_hashes')
    mocker.patch('upsies.utils.torrent._store_generic_torrent')

    with pytest.raises(errors.TorrentError, match=rf'^{re.escape(exp_error)}$'):
        torrent.create(
            content_path='/path/to/content',
            torrent_path='/path/to/content.torrent',
            announce=announce,
            source=source,
            init_callback=Mock(),
            progress_callback=Mock(),
            exclude=('a', 'b', 'c'),
        )
    assert torrent._get_torrent.call_args_list == []
    assert torrent._make_file_tree.call_args_list == []
    assert torrent._find_hashes.call_args_list == []
    assert torrent._generate_hashes.call_args_list == []
    assert torrent._store_generic_torrent.call_args_list == []


@pytest.mark.parametrize(
    argnames='init_cb_cancels, find_hashes_cancels, generate_hashes_cancels',
    argvalues=(
        pytest.param(False, False, False, id='nothing cancels'),
        pytest.param(True, False, False, id='init_callback cancels'),
        pytest.param(False, True, False, id='find_hashes cancels'),
        pytest.param(False, False, True, id='generate_hashes cancels'),
    ),
)
@pytest.mark.parametrize(
    argnames='use_cache, find_hashes_succeeds',
    argvalues=(
        pytest.param(True, True, id='find hash successfully'),
        pytest.param(False, False, id='do not try to find hash'),
    ),
)
def test_create(use_cache, find_hashes_succeeds,
                init_cb_cancels, find_hashes_cancels, generate_hashes_cancels, mocker):
    def find_hashes_side_effect(**_):
        mock_torrent.is_ready = find_hashes_succeeds
        return find_hashes_cancels

    mocks = Mock()
    mock_torrent = Mock(is_ready=False)
    mocks.attach_mock(mocker.patch('upsies.utils.torrent._get_torrent', return_value=mock_torrent), 'get_torrent')
    mocks.attach_mock(mocker.patch('upsies.utils.torrent._make_file_tree'), 'make_file_tree')
    mocks.attach_mock(mocker.patch('upsies.utils.torrent._find_hashes', side_effect=find_hashes_side_effect), 'find_hashes')
    mocks.attach_mock(mocker.patch('upsies.utils.torrent._generate_hashes', return_value=generate_hashes_cancels), 'generate_hashes')
    mocks.attach_mock(mocker.patch('upsies.utils.torrent._store_generic_torrent'), 'store_generic_torrent')
    mocks.attach_mock(mocker.patch('upsies.utils.torrent._write_torrent_path'), 'write_torrent_path')
    mocks.attach_mock(Mock(return_value=init_cb_cancels), 'init_callback')
    mocks.attach_mock(Mock(), 'progress_callback')

    torrent_path = '/path/to/content.torrent'
    content_path = '/path/to/content'
    exclude = ('a', 'b', 'c')
    reuse_torrent_path = 'path/to/existing.torrent'
    announce = 'https://tracker.foo/announce'
    source = 'ASDF'

    kwargs = {
        'torrent_path': torrent_path,
        'content_path': content_path,
        'exclude': exclude,
        'use_cache': use_cache,
        'reuse_torrent_path': reuse_torrent_path,
        'announce': announce,
        'source': source,
        'init_callback': mocks.init_callback,
        'progress_callback': mocks.progress_callback,
    }

    return_value = torrent.create(**kwargs)

    exp_mock_calls = [
        call.get_torrent(
            content_path=content_path,
            exclude=exclude,
            announce=announce,
            source=source,
        ),
        call.make_file_tree(mock_torrent.filetree),
        call.init_callback(mocks.make_file_tree.return_value),
    ]

    if not init_cb_cancels and use_cache:
        exp_mock_calls.append(call.find_hashes(
            torrent=mocks.get_torrent.return_value,
            reuse_torrent_path=reuse_torrent_path,
            callback=mocks.progress_callback,
        ))

    if (
            not init_cb_cancels
            and ((not use_cache or (use_cache and not find_hashes_cancels))
                 and not find_hashes_succeeds)
    ):
        exp_mock_calls.append(call.generate_hashes(
            torrent=mocks.get_torrent.return_value,
            callback=mocks.progress_callback,
        ))

    if (
            not init_cb_cancels
            and (not use_cache or not find_hashes_cancels)
            and (find_hashes_succeeds or not generate_hashes_cancels)
    ):
        exp_mock_calls.extend((
            call.store_generic_torrent(mocks.get_torrent.return_value),
            call.write_torrent_path(mocks.get_torrent.return_value, torrent_path),
        ))
        assert return_value == torrent_path
    else:
        assert return_value is None

    assert mocks.mock_calls == exp_mock_calls


@pytest.mark.parametrize(
    argnames='exception, exp_exception',
    argvalues=(
        (None, None),
        (torf.TorfError('foo'), errors.TorrentError('foo')),
    ),
    ids=lambda v: repr(v),
)
def test_get_torrent(exception, exp_exception, mocker):
    Torrent_mock = mocker.patch('torf.Torrent', side_effect=exception)
    with patch('time.time', return_value='mock time'):
        if exp_exception:
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
                torrent._get_torrent(
                    content_path='path/to/content',
                    exclude=('foo', 'bar'),
                    announce='http://localhost:123/announce',
                    source='ASDF',
                )
        else:
            return_value = torrent._get_torrent(
                content_path='path/to/content',
                exclude=('foo', 'bar'),
                announce='http://localhost:123/announce',
                source='ASDF',
            )
            assert return_value is Torrent_mock.return_value

    assert Torrent_mock.call_args_list == [call(
        path='path/to/content',
        exclude_regexs=('foo', 'bar'),
        trackers=(('http://localhost:123/announce',),),
        source='ASDF',
        private=True,
        created_by=f'{__project_name__} {__version__}',
        creation_date='mock time',
    )]


@pytest.mark.parametrize(
    argnames='exception, exp_exception',
    argvalues=(
        (None, None),
        (torf.TorfError('foo'), errors.TorrentError('foo')),
    ),
    ids=lambda v: repr(v),
)
def test_generate_hashes(exception, exp_exception, mocker):
    CreateTorrentCallback_mock = mocker.patch('upsies.utils.torrent._CreateTorrentCallback')
    callback = Mock()
    mock_torrent = Mock(generate=Mock(side_effect=exception))

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            torrent._generate_hashes(
                torrent=mock_torrent,
                callback=callback,
            )
    else:
        return_value = torrent._generate_hashes(
            torrent=mock_torrent,
            callback=callback,
        )
        assert return_value is CreateTorrentCallback_mock.return_value.return_value

    assert CreateTorrentCallback_mock.call_args_list == [call(callback)]
    assert mock_torrent.generate.call_args_list == [call(
        callback=CreateTorrentCallback_mock.return_value,
        interval=1.0,
    )]


@pytest.mark.parametrize(
    argnames='exception, exp_exception',
    argvalues=(
        (None, None),
        (torf.TorfError('foo'), errors.TorrentError('foo')),
    ),
    ids=lambda v: repr(v),
)
def test_find_hashes(exception, exp_exception, mocker):
    FindTorrentCallback_mock = mocker.patch('upsies.utils.torrent._FindTorrentCallback')
    get_reuse_torrent_paths_mock = mocker.patch('upsies.utils.torrent._get_reuse_torrent_paths')
    callback = Mock()
    mock_torrent = Mock(reuse=Mock(side_effect=exception))

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            torrent._find_hashes(
                torrent=mock_torrent,
                reuse_torrent_path='path/to/existing/torrents/',
                callback=callback,
            )
    else:
        return_value = torrent._find_hashes(
            torrent=mock_torrent,
            reuse_torrent_path='path/to/existing/torrents/',
            callback=callback,
        )
        assert return_value is FindTorrentCallback_mock.return_value.return_value

    assert FindTorrentCallback_mock.call_args_list == [call(callback)]
    assert mock_torrent.reuse.call_args_list == [call(
        get_reuse_torrent_paths_mock.return_value,
        callback=FindTorrentCallback_mock.return_value,
        interval=1.0,
    )]


@pytest.mark.parametrize(
    argnames='reuse_torrent_path, exp_result',
    argvalues=(
        (None, []),
        ((), []),
        ('path/to/existing/torrents', ['path/to/existing/torrents']),
        (('path/to/torrents1', 'path/to/torrents2'), ['path/to/torrents1', 'path/to/torrents2']),
        (123, ValueError('Invalid reuse_torrent_path: 123')),
    ),
    ids=lambda v: repr(v),
)
def test_get_reuse_torrent_paths(reuse_torrent_path, exp_result, mocker):
    get_generic_torrent_path_mock = mocker.patch('upsies.utils.torrent._get_generic_torrent_path')
    mock_torrent = Mock()

    if isinstance(exp_result, Exception):
        with pytest.raises(type(exp_result), match=rf'^{re.escape(str(exp_result))}$'):
            torrent._get_reuse_torrent_paths(mock_torrent, reuse_torrent_path)
    else:
        return_value = torrent._get_reuse_torrent_paths(mock_torrent, reuse_torrent_path)
        assert return_value == [
            get_generic_torrent_path_mock.return_value,
        ] + exp_result

        assert get_generic_torrent_path_mock.call_args_list == [
            call(torrent=mock_torrent, create_directory=False),
        ]


def test_store_generic_torrent(mocker):
    Torrent_mock = mocker.patch('torf.Torrent')
    copy_torrent_info_mock = mocker.patch('upsies.utils.torrent._copy_torrent_info')
    get_generic_torrent_path_mock = mocker.patch('upsies.utils.torrent._get_generic_torrent_path')
    generic_torrent = Torrent_mock.return_value

    with patch('time.time', return_value='mock time'):
        torrent._store_generic_torrent(torrent)

    assert Torrent_mock.call_args_list == [call(
        private=True,
        created_by=f'{__project_name__} {__version__}',
        creation_date='mock time',
        comment='This torrent is used to cache previously hashed pieces.',
    )]
    assert copy_torrent_info_mock.call_args_list == [call(torrent, generic_torrent)]
    assert get_generic_torrent_path_mock.call_args_list == [
        call(generic_torrent, create_directory=True),
    ]
    assert generic_torrent.write.call_args_list == [call(
        get_generic_torrent_path_mock.return_value,
        overwrite=True,
    )]


@pytest.mark.parametrize(
    argnames='exception, exp_exception',
    argvalues=(
        (None, None),
        (torf.TorfError('foo'), errors.TorrentError('foo')),
    ),
    ids=lambda v: repr(v),
)
def test_write_torrent_path(exception, exp_exception, mocker):
    mock_torrent = Mock(write=Mock(side_effect=exception))
    torrent_path = 'path/to/my.torrent'

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            torrent._write_torrent_path(mock_torrent, torrent_path)
    else:
        torrent._write_torrent_path(mock_torrent, torrent_path)

    assert mock_torrent.write.call_args_list == [
        call(torrent_path, overwrite=True),
    ]


@pytest.mark.parametrize(
    argnames='GENERIC_TORRENTS_DIRPATH, create_directory, exception, exp_exception',
    argvalues=(
        ('/generic/torrents', False, errors.ContentError('foo'), None),
        ('/generic/torrents', True, errors.ContentError('foo'), errors.TorrentError('/generic/torrents: foo')),
        ('/generic/torrents', True, None, None),
    ),
    ids=lambda v: repr(v),
)
def test_get_generic_torrent_path(GENERIC_TORRENTS_DIRPATH, create_directory, exception, exp_exception, mocker):
    mocker.patch('upsies.constants.GENERIC_TORRENTS_DIRPATH', GENERIC_TORRENTS_DIRPATH)
    mkdir_mock = mocker.patch('upsies.utils.fs.mkdir', side_effect=exception)
    get_torrent_id_mock = mocker.patch('upsies.utils.torrent._get_torrent_id')
    mock_torrent = Mock()
    mock_torrent.configure_mock(name='My Torrent')

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            torrent._get_generic_torrent_path(mock_torrent, create_directory=create_directory)
    else:
        return_value = torrent._get_generic_torrent_path(mock_torrent, create_directory=create_directory)

    if create_directory:
        assert mkdir_mock.call_args_list == [call(GENERIC_TORRENTS_DIRPATH)]

    if not exp_exception:
        assert get_torrent_id_mock.call_args_list == [call(mock_torrent)]
        assert return_value == os.path.join(
            GENERIC_TORRENTS_DIRPATH,
            f'{mock_torrent.name}.{get_torrent_id_mock.return_value}.torrent',
        )


def test_get_torrent_id_info(mocker):
    class MockFile(str):
        def __new__(cls, string, size):
            self = super().__new__(cls, string)
            self.size = size
            return self

    mock_torrent = Mock()
    mock_torrent.configure_mock(
        name='My Torrent',
        files=[
            MockFile('foo', size=123),
            MockFile('bar', size=234),
        ],
    )

    return_value = torrent._get_torrent_id_info(mock_torrent)
    assert return_value == {
        'name': 'My Torrent',
        'files': (
            ('foo', 123),
            ('bar', 234),
        ),
    }


def test_get_torrent_id(mocker):
    get_torrent_id_info_mock = mocker.patch('upsies.utils.torrent._get_torrent_id_info')
    semantic_hash_mock = mocker.patch('upsies.utils.semantic_hash')

    mock_torrent = Mock()
    return_value = torrent._get_torrent_id(mock_torrent)
    assert return_value is semantic_hash_mock.return_value
    assert semantic_hash_mock.call_args_list == [call(get_torrent_id_info_mock.return_value)]
    assert get_torrent_id_info_mock.call_args_list == [call(mock_torrent)]


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
            },
        },
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


@pytest.fixture
def TestCallback():
    class TestCallback(torrent._CallbackBase):
        pass
    return TestCallback

def test_CallbackBase_return_value_attribute(TestCallback):
    return_value = Mock()
    cb = Mock(return_value=return_value)
    mock_cb = TestCallback(cb)
    assert mock_cb.return_value is None
    assert mock_cb('mock progress') is return_value
    assert mock_cb.return_value is return_value
    assert cb.call_args_list == [call('mock progress')]


@pytest.mark.parametrize(
    argnames='time_started, time_current, items_done, items_total, samples',
    argvalues=(
        (100, 160, 200, 300, []),
        (100, 160, 156, 300, [(163, 138), (166, 147)]),
        (100, 112, 60, 300, [(103, 51), (106, 54), (109, 57)]),
        (100, 112, 27, 90, [(100, 27), (101, 27), (102, 27), (103, 27)]),
    ),
    ids=lambda v: repr(v),
)
def test_CallbackBase_calculate_info(time_started, time_current, items_done, items_total, samples, TestCallback, mocker):
    exp_info = {}
    exp_info['percent_done'] = items_done / items_total * 100
    if len(samples) >= 2:
        exp_info['items_per_second'] = (samples[-1][1] - samples[0][1]) / (len(samples) - 1)
    else:
        exp_info['items_per_second'] = 0
    exp_info['items_remaining'] = items_total - items_done
    if exp_info['items_per_second'] > 0:
        exp_info['seconds_remaining'] = datetime.timedelta(seconds=exp_info['items_remaining'] / exp_info['items_per_second'])
    else:
        exp_info['seconds_remaining'] = datetime.timedelta(seconds=0)
    exp_info['seconds_elapsed'] = datetime.timedelta(seconds=time_current - time_started)
    exp_info['seconds_total'] = datetime.timedelta(seconds=(
        time_current - time_started
        + exp_info['seconds_remaining'].total_seconds()
    ))
    exp_info['time_finished'] = datetime.datetime.fromtimestamp(time_current + exp_info['seconds_remaining'].total_seconds())
    exp_info['time_started'] = datetime.datetime.fromtimestamp(time_started)

    add_sample_mock = mocker.patch('upsies.utils.torrent._CallbackBase._add_sample')
    get_average_mock = mocker.patch('upsies.utils.torrent._CallbackBase._get_average')
    get_average_mock.side_effect = lambda diffs, **kw: sum(diffs) / len(diffs)

    cb = TestCallback(Mock())
    cb._time_started = time_started
    cb._progress_samples = samples

    with patch('time.time', return_value=time_current):
        info = cb._calculate_info(items_done, items_total)
    assert info == exp_info

    assert add_sample_mock.call_args_list == [call(time_current, items_done)]

    if samples:
        exp_diffs = [
            b[1] - a[1]
            for a, b in zip(samples[:-1], samples[1:])
        ]
        assert get_average_mock.call_args_list == [call(exp_diffs, weight_factor=1.1)]
    else:
        assert get_average_mock.call_args_list == []


@pytest.mark.parametrize(
    argnames='rounds, interval, items_to_keep',
    argvalues=(
        (15, 6, 2),
        (15, 5, 3),
        (15, 4, 3),
        (15, 3, 4),
        (15, 2, 6),
        (15, 1, 11),
    ),
    ids=lambda v: repr(v),
)
def test_CallbackBase_add_sample(rounds, interval, items_to_keep, TestCallback):
    time_now_pool = iter(range(1000, 2000, interval))
    items_done_pool = iter(range(0, 100, 3))
    exp_progress_samples = []

    cb = TestCallback(Mock())
    assert cb._progress_samples == exp_progress_samples

    for i in range(rounds + 1):
        time_now = next(time_now_pool)
        items_done = next(items_done_pool)
        cb._add_sample(time_now, items_done)

        exp_progress_samples.append((time_now, items_done))
        del exp_progress_samples[:-items_to_keep]

        assert cb._progress_samples == exp_progress_samples


@pytest.mark.parametrize(
    argnames='weight_factor, samples, exp_average',
    argvalues=(
        (1.0, [1, 2, 3, 6, 5, 1], (1 + 2 + 3 + 6 + 5 + 1) / 6),  # sum(samples) = 18 / len(samples) = 6
        (2.0, [3, 2, 6, 15], (
            ((3 * 2) + (2 * 4) + (6 * 8) + (15 * 16))
            / (2 + 4 + 8 + 16)
        )),
        (3.0, [9, 9, 8, 3], (
            ((9 * 3) + (9 * 9) + (8 * 27) + (3 * 81))
            / (3 + 9 + 27 + 81)
        )),
    ),
    ids=lambda v: repr(v),
)
def test_CallbackBase_get_average(weight_factor, samples, exp_average, TestCallback):
    cb = TestCallback(Mock())
    average = cb._get_average(samples, weight_factor)
    assert average == exp_average


def test_CreateTorrentCallback(mocker):
    call_mock = mocker.patch('upsies.utils.torrent._CallbackBase.__call__')
    mocker.patch('upsies.utils.torrent._CreateTorrentCallback._calculate_info', return_value={
        'items_per_second': 100,
        'percent_done': 200,
        'seconds_elapsed': 300,
        'seconds_remaining': 400,
        'seconds_total': 500,
        'time_finished': 600,
        'time_started': 700,
    })

    cb = torrent._CreateTorrentCallback(Mock())
    return_value = cb(
        torrent=Mock(piece_size=123, size=456),
        filepath='path/to/file',
        pieces_done=23,
        pieces_total=42,
    )
    assert return_value is call_mock.return_value
    assert call_mock.call_args_list == [call(torrent.CreateTorrentProgress(
        pieces_done=23,
        pieces_total=42,
        percent_done=200,
        bytes_per_second=types.Bytes(100 * 123),
        piece_size=123,
        total_size=456,
        filepath='path/to/file',
        seconds_elapsed=300,
        seconds_remaining=400,
        seconds_total=500,
        time_finished=600,
        time_started=700,
    ))]
    assert cb._calculate_info.call_args_list == [call(23, 42)]


@pytest.mark.parametrize(
    argnames='exception, exp_exception',
    argvalues=(
        (None, None),
        (OSError('foo'), errors.TorrentError('foo')),
        (torf.TorfError('foo'), errors.TorrentError('foo')),
        (torf.ReadError(errno=errno.EACCES, path='foo'), errors.TorrentError('foo: Permission denied')),
        (torf.ReadError(errno=errno.ENOENT, path='foo'), None),
    ),
    ids=lambda v: repr(v),
)
def test_FindTorrentCallback(exception, exp_exception, mocker):
    call_mock = mocker.patch('upsies.utils.torrent._CallbackBase.__call__')
    mocker.patch('upsies.utils.torrent._FindTorrentCallback._calculate_info', return_value={
        'items_per_second': 100,
        'percent_done': 200,
        'seconds_elapsed': 300,
        'seconds_remaining': 400,
        'seconds_total': 500,
        'time_finished': 600,
        'time_started': 700,
    })
    cb = torrent._FindTorrentCallback(Mock())
    return_value = cb(
        torrent=Mock(piece_size=123, size=456),
        filepath='path/to/file',
        files_done=23,
        files_total=42,
        status='current status',
        exception=exception,
    )
    assert return_value is call_mock.return_value
    assert call_mock.call_args_list == [call(torrent.FindTorrentProgress(
        files_done=23,
        files_total=42,
        percent_done=200,
        files_per_second=100,
        filepath='path/to/file',
        status='current status',
        exception=exp_exception,
        seconds_elapsed=300,
        seconds_remaining=400,
        seconds_total=500,
        time_finished=600,
        time_started=700,
    ))]
    assert cb._calculate_info.call_args_list == [call(23, 42)]
