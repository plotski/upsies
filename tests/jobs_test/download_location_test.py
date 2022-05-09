import errno
import os
import re
from unittest.mock import Mock, PropertyMock, call

import pytest
import torf

from upsies.jobs import download_location


class MockFile(str):
    def __new__(cls, filepath, size):
        self = super().__new__(cls, filepath)
        self.size = size
        return self


def test_DownloadLocationJob_name():
    assert download_location.DownloadLocationJob.name == 'download-location'


def test_DownloadLocationJob_label():
    assert download_location.DownloadLocationJob.label == 'Download Location'


def test_DownloadLocationJob_hidden():
    assert download_location.DownloadLocationJob.hidden is True


def test_DownloadLocationJob_cache_id():
    assert download_location.DownloadLocationJob.cache_id is None


@pytest.mark.parametrize(
    argnames='locations, default, torf_error, target_location, exp_get_target_location_calls, exp_errors, exp_output',
    argvalues=(
        ((), None, None, None, [], ('You must provide at least one location.',), ()),
        (('a', 'b', 'c'), None, torf.TorfError('nope'), None, [], (torf.TorfError('nope'),), ()),
        (('a', 'b', 'c',), None, None, 'download/path', [call()], (), ('download/path',)),
        (('a', 'b', 'c',), 'default/path', None, 'download/path', [call()], (), ('download/path',)),
        (('a', 'b', 'c',), 'default/path', None, None, [call()], (), ('default/path',)),
        (('a', 'b', 'c',), None, None, None, [call()], (), ('a',)),
    ),
)
def test_DownloadLocationJob_execute(locations, default, torf_error, target_location,
                                     exp_get_target_location_calls, exp_errors, exp_output,
                                     mocker, tmp_path):
    dlj = download_location.DownloadLocationJob(
        torrent='mock.torrent',
        locations=locations,
        default=default,
    )
    mocker.patch.object(dlj, '_get_target_location', return_value=target_location)
    if torf_error:
        mocker.patch('torf.Torrent.read', side_effect=torf_error)
    else:
        mocker.patch('torf.Torrent.read', return_value='mock torrent object')

    dlj.execute()

    assert dlj._get_target_location.call_args_list == exp_get_target_location_calls

    if locations and not torf_error:
        assert dlj._torrent == 'mock torrent object'
    else:
        assert dlj._torrent is None

    assert [type(e) for e in dlj.errors] == [type(exp_e) for exp_e in exp_errors]
    assert [str(e) for e in dlj.errors] == [str(exp_e) for exp_e in exp_errors]
    assert dlj.output == exp_output
    assert dlj.raised is None
    assert dlj.is_finished


@pytest.mark.parametrize(
    argnames='file_candidates, exp_target_location',
    argvalues=(
        (
            # file_candidates
            {
                'foo/1': [
                    {'filepath': 'this/FOO/one', 'location': 'this'},
                ],
                'foo/bar/2': [
                    {'filepath': 'this/Foo/two.corrupt', 'location': 'this'},
                    {'filepath': 'that/Foo/two', 'location': 'that'},
                ],
                'foo/bar/baz/3': [
                    {'filepath': 'that/foo/barz/three', 'location': 'that'},
                ],
            },
            # exp_target_location
            'this',
        ),
    ),
)
def test_DownloadLocationJob_get_target_location(file_candidates, exp_target_location, mocker, tmp_path):
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(type(dlj), 'cache_directory', PropertyMock(return_value=tmp_path))
    mocker.patch.object(dlj, '_create_hardlink')

    for file, candidates in tuple(file_candidates.items()):
        for i,candidate in enumerate(candidates):
            candidates[i]['filepath'] = tmp_path / candidate['filepath']
            candidates[i]['location'] = tmp_path / candidate['location']
            candidate['filepath'].parent.mkdir(parents=True, exist_ok=True)
            if 'corrupt' in candidate['filepath'].name:
                candidate['filepath'].write_text('corrupt')
            else:
                candidate['filepath'].write_text('good')

    mocker.patch.object(dlj, '_get_file_candidates', return_value=file_candidates)

    def verify_file_mock(file):
        filepath = os.path.join(dlj._check_location, file)
        with open(filepath, 'r') as f:
            return f.read() == 'good'

    mocker.patch.object(dlj, '_verify_file', side_effect=verify_file_mock)

    assert dlj._get_target_location() == tmp_path / exp_target_location


@pytest.mark.parametrize(
    argnames='piece_indexes, verify_piece_return_values, exp_verify_piece_calls, exp_return_value',
    argvalues=(
        ([1, 5, 11], [True, True, True], [call(1), call(5), call(11)], True),

        ([1, 5, 11], [True, True, False], [call(1), call(5), call(11)], False),
        ([1, 5, 11], [True, False, True], [call(1), call(5)], False),
        ([1, 5, 11], [False, True, True], [call(1)], False),

        ([1, 5, 11], [True, True, None], [call(1), call(5), call(11)], None),
        ([1, 5, 11], [True, None, True], [call(1), call(5)], None),
        ([1, 5, 11], [None, True, True], [call(1)], None),
    ),
)
def test_DownloadLocationJob_verify_file(piece_indexes, verify_piece_return_values, exp_verify_piece_calls,
                                         exp_return_value, mocker, tmp_path):
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(dlj, '_torrent')
    TorrentFileStream_mock = mocker.patch('torf.TorrentFileStream')
    tfs_mock = TorrentFileStream_mock.return_value.__enter__.return_value
    tfs_mock.get_absolute_piece_indexes.return_value = piece_indexes
    tfs_mock.verify_piece.side_effect = verify_piece_return_values

    assert dlj._verify_file('mock/file/path') is exp_return_value

    exp_content_path = os.path.join(dlj._check_location, dlj._torrent.name)
    assert TorrentFileStream_mock.call_args_list == [call(dlj._torrent, content_path=exp_content_path)]
    assert tfs_mock.get_absolute_piece_indexes.call_args_list == [call('mock/file/path', (1, -2))]
    assert tfs_mock.verify_piece.call_args_list == exp_verify_piece_calls


def test_DownloadLocationJob_each_set_of_linked_candidates(mocker, tmp_path):
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(dlj, '_create_symlink')
    mocker.patch.object(dlj, '_remove_link')

    location = tmp_path / 'links'
    file_candidates = {
        'a': [{'filepath': 'a1'}],
        'b': [{'filepath': 'b1'}, {'filepath': 'b2'}],
        'c': [{'filepath': 'c1'}, {'filepath': 'c2'}, {'filepath': 'c3'}],
    }
    exp = [
        (
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b1'}, 'c': {'filepath': 'c1'}},
            [
                call(os.path.abspath('a1'), os.path.join(location, 'a')),
                call(os.path.abspath('b1'), os.path.join(location, 'b')),
                call(os.path.abspath('c1'), os.path.join(location, 'c')),
            ],
            [],
        ),
        (
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b1'}, 'c': {'filepath': 'c2'}},
            [
                call(os.path.abspath('a1'), os.path.join(location, 'a')),
                call(os.path.abspath('b1'), os.path.join(location, 'b')),
                call(os.path.abspath('c2'), os.path.join(location, 'c')),
            ],
            [call(os.path.join(location, 'a')), call(os.path.join(location, 'b')), call(os.path.join(location, 'c'))],
        ),
        (
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b1'}, 'c': {'filepath': 'c3'}},
            [
                call(os.path.abspath('a1'), os.path.join(location, 'a')),
                call(os.path.abspath('b1'), os.path.join(location, 'b')),
                call(os.path.abspath('c3'), os.path.join(location, 'c')),
            ],
            [call(os.path.join(location, 'a')), call(os.path.join(location, 'b')), call(os.path.join(location, 'c'))],
        ),
        (
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b2'}, 'c': {'filepath': 'c1'}},
            [
                call(os.path.abspath('a1'), os.path.join(location, 'a')),
                call(os.path.abspath('b2'), os.path.join(location, 'b')),
                call(os.path.abspath('c1'), os.path.join(location, 'c')),
            ],
            [call(os.path.join(location, 'a')), call(os.path.join(location, 'b')), call(os.path.join(location, 'c'))],
        ),
        (
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b2'}, 'c': {'filepath': 'c2'}},
            [
                call(os.path.abspath('a1'), os.path.join(location, 'a')),
                call(os.path.abspath('b2'), os.path.join(location, 'b')),
                call(os.path.abspath('c2'), os.path.join(location, 'c')),
            ],
            [call(os.path.join(location, 'a')), call(os.path.join(location, 'b')), call(os.path.join(location, 'c'))],
        ),
        (
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b2'}, 'c': {'filepath': 'c3'}},
            [
                call(os.path.abspath('a1'), os.path.join(location, 'a')),
                call(os.path.abspath('b2'), os.path.join(location, 'b')),
                call(os.path.abspath('c3'), os.path.join(location, 'c')),
            ],
            [call(os.path.join(location, 'a')), call(os.path.join(location, 'b')), call(os.path.join(location, 'c'))],
        ),
    ]

    for paths in dlj._each_set_of_linked_candidates(location, file_candidates):
        paths, create_symlink_calls, remove_link_calls = exp.pop(0)
        assert paths == paths
        assert dlj._create_symlink.call_args_list == create_symlink_calls
        assert dlj._remove_link.call_args_list == remove_link_calls
        dlj._create_symlink.reset_mock()
        dlj._remove_link.reset_mock()


def test_DownloadLocationJob_get_file_candidates(mocker, tmp_path):
    files = (
        tmp_path / '.1',
        tmp_path / '.2',
        tmp_path / '.3',
        tmp_path / 'a' / 'a1',
        tmp_path / 'a' / 'a2',
        tmp_path / 'a' / 'a3',
        tmp_path / 'a' / 'b' / 'ab1',
        tmp_path / 'a' / 'b' / 'ab2',
        tmp_path / 'a' / 'b' / 'ab3',
        tmp_path / 'c' / 'c1',
        tmp_path / 'c' / 'c2',
        tmp_path / 'c' / 'c3',
    )
    for f in files:
        f.parent.mkdir(parents=True, exist_ok=True)
        filesize = int(f.name[-1])
        f.write_bytes(b'x' * filesize)

    dlj = download_location.DownloadLocationJob(
        torrent='mock.torrent',
        locations=(
            tmp_path / 'a',
            tmp_path / 'c',
        ),
    )
    mocker.patch.object(dlj, '_torrent', Mock(files=(
        # Same path
        MockFile('a/a1', size=1),
        # Same path, different file name
        MockFile('a/b/ab.2', size=2),
        # Different path, different file name
        MockFile('c/d/c3', size=3),
        # No matches
        MockFile('foo/bar0', size=0),
        MockFile('foo/baz4', size=4),
    )))

    exp_file_candidates = {
        str('a/a1'): [
            {'location': str(tmp_path / 'a'), 'filepath': str(tmp_path / 'a/a1'),
             'filepath_rel': 'a1', 'similarity': 0.6666666666666666},
        ],
        str('a/b/ab.2'): [
            {'location': str(tmp_path / 'a'), 'filepath': str(tmp_path / 'a/b/ab2'),
             'filepath_rel': 'b/ab2', 'similarity': 0.7692307692307693},
        ],
        str('c/d/c3'): [
            {'location': str(tmp_path / 'c'), 'filepath': str(tmp_path / 'c/c3'),
             'filepath_rel': 'c3', 'similarity': 0.5},
        ],
    }
    file_candidates = dlj._get_file_candidates()

    # for file, cands in file_candidates.items():
    #     print(file)
    #     for c in cands:
    #         print('  ', c)
    # print('--------------')
    # for file, cands in exp_file_candidates.items():
    #     print(file)
    #     for c in cands:
    #         print('  ', c)

    assert file_candidates == exp_file_candidates


def test_DownloadLocationJob_each_file(tmp_path):
    files = (
        tmp_path / '1',
        tmp_path / 'a' / '2',
        tmp_path / 'a' / '3',
        tmp_path / 'a' / 'b' / '4',
        tmp_path / 'a' / 'b' / '5',
        tmp_path / 'a' / 'b' / '6',
        tmp_path / 'c' / '7',
        tmp_path / 'c' / '8',
    )
    for f in files:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b'mock data')

    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    assert sorted(dlj._each_file(tmp_path / 'a')) == [
        (str(tmp_path / 'a' / '2'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / '3'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '4'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '5'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '6'), str(tmp_path / 'a')),
    ]
    assert sorted(dlj._each_file(tmp_path / 'a', tmp_path / 'c' / '8')) == [
        (str(tmp_path / 'a' / '2'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / '3'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '4'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '5'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '6'), str(tmp_path / 'a')),
        (str(tmp_path / 'c' / '8'), str(tmp_path / 'c' / '8')),
    ]
    assert sorted(dlj._each_file(tmp_path / 'a', tmp_path / 'c')) == [
        (str(tmp_path / 'a' / '2'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / '3'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '4'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '5'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '6'), str(tmp_path / 'a')),
        (str(tmp_path / 'c' / '7'), str(tmp_path / 'c')),
        (str(tmp_path / 'c' / '8'), str(tmp_path / 'c')),
    ]
    assert sorted(dlj._each_file(tmp_path / 'a' / 'b', tmp_path / 'c')) == [
        (str(tmp_path / 'a' / 'b' / '4'), str(tmp_path / 'a' / 'b')),
        (str(tmp_path / 'a' / 'b' / '5'), str(tmp_path / 'a' / 'b')),
        (str(tmp_path / 'a' / 'b' / '6'), str(tmp_path / 'a' / 'b')),
        (str(tmp_path / 'c' / '7'), str(tmp_path / 'c')),
        (str(tmp_path / 'c' / '8'), str(tmp_path / 'c')),
    ]


def test_DownloadLocationJob_is_size_match(mocker):
    file_size_mock = mocker.patch('upsies.utils.fs.file_size', return_value=456)
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    files = (Mock(size=123), Mock(size=456), Mock(size=789))
    assert dlj._is_size_match(files[0], 'path/to/foo') is False
    assert file_size_mock.call_args_list == [call('path/to/foo')]
    assert dlj._is_size_match(files[1], 'path/to/bar') is True
    assert file_size_mock.call_args_list == [call('path/to/foo'), call('path/to/bar')]
    assert dlj._is_size_match(files[2], 'path/to/baz') is False
    assert file_size_mock.call_args_list == [call('path/to/foo'), call('path/to/bar'), call('path/to/baz')]


def test_DownloadLocationJob_create_hardlink(mocker):
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(dlj, '_create_link', Mock(return_value='foo'))
    assert dlj._create_hardlink('path/to/source', 'path/to/target') == 'foo'
    assert dlj._create_link.call_args_list == [
        call(dlj._hardlink_or_symlink, 'path/to/source', 'path/to/target'),
    ]


@pytest.mark.parametrize(
    argnames='hardlink_exception, symlink_exception, exp_exception',
    argvalues=(
        (None, None, None),
        (None, OSError(errno.EACCES, 'Permission'), None),
        (OSError(errno.EACCES, 'Permission'), None, OSError(errno.EACCES, 'Permission')),
        (OSError(errno.EXDEV, 'Cross-device'), None, None),
        (OSError(errno.EXDEV, 'Cross-device'), OSError(errno.EACCES, 'Permission'), OSError(errno.EACCES, 'Permission')),
    ),
)
def test_DownloadLocationJob_hardlink_or_symlink(hardlink_exception, symlink_exception, exp_exception, mocker):
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    hardlink_mock = mocker.patch('os.link', Mock(side_effect=hardlink_exception))
    symlink_mock = mocker.patch('os.symlink', Mock(side_effect=symlink_exception))
    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            dlj._hardlink_or_symlink('path/to/source', 'path/to/target')
    else:
        assert dlj._hardlink_or_symlink('path/to/source', 'path/to/target') is None

    assert hardlink_mock.call_args_list == [call('path/to/source', 'path/to/target')]
    if hardlink_exception and hardlink_exception.errno == errno.EXDEV:
        assert symlink_mock.call_args_list == [call('path/to/source', 'path/to/target')]
    else:
        assert symlink_mock.call_args_list == []


def test_DownloadLocationJob_create_symlink(mocker):
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(dlj, '_create_link', Mock(return_value='foo'))
    assert dlj._create_symlink('path/to/source', 'path/to/target') == 'foo'
    import os
    assert dlj._create_link.call_args_list == [call(os.symlink, 'path/to/source', 'path/to/target')]


def test_DownloadLocationJob_create_link_that_already_exists(mocker):
    exists_mock = mocker.patch('os.path.exists', return_value=True)
    makedirs_mock = mocker.patch('os.makedirs')
    create_link_function = Mock(__qualname__='mylink')
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    dlj._create_link(create_link_function, 'path/to/source', 'path/to/target')
    assert exists_mock.call_args_list == [call('path/to/target')]
    assert makedirs_mock.call_args_list == []
    assert create_link_function.call_args_list == []
    assert dlj.output == ()
    assert dlj.errors == ()
    assert dlj.raised is None
    assert dlj._links_created == {}

def test_DownloadLocationJob_create_link_fails_to_create_parent_directories(mocker):
    exists_mock = mocker.patch('os.path.exists', return_value=False)
    makedirs_mock = mocker.patch('os.makedirs', side_effect=OSError('nope'))
    create_link_function = Mock(__qualname__='mylink')
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    dlj._create_link(create_link_function, 'path/to/source', 'path/to/target')
    assert exists_mock.call_args_list == [call('path/to/target')]
    assert makedirs_mock.call_args_list == [call('path/to', exist_ok=True)]
    assert create_link_function.call_args_list == []
    assert dlj.output == ()
    assert dlj.errors == ('Failed to create directory: path/to: nope',)
    assert dlj.raised is None
    assert dlj._links_created == {}

def test_DownloadLocationJob_create_link_fails_to_create_link(mocker):
    exists_mock = mocker.patch('os.path.exists', return_value=False)
    makedirs_mock = mocker.patch('os.makedirs')
    create_link_function = Mock(__qualname__='mylink', side_effect=OSError('nope'))
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    dlj._create_link(create_link_function, 'path/to/source', 'path/to/target')
    assert exists_mock.call_args_list == [call('path/to/target')]
    assert makedirs_mock.call_args_list == [call('path/to', exist_ok=True)]
    assert create_link_function.call_args_list == [call('path/to/source', 'path/to/target')]
    assert dlj.output == ()
    assert dlj.errors == ('Failed to create link: path/to/target: nope',)
    assert dlj.raised is None
    assert dlj._links_created == {}

def test_DownloadLocationJob_create_link_creates_link(mocker):
    exists_mock = mocker.patch('os.path.exists', return_value=False)
    makedirs_mock = mocker.patch('os.makedirs')
    create_link_function = Mock(__qualname__='mylink')
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    dlj._create_link(create_link_function, 'path/to/source', 'path/to/target')
    assert exists_mock.call_args_list == [call('path/to/target')]
    assert makedirs_mock.call_args_list == [call('path/to', exist_ok=True)]
    assert create_link_function.call_args_list == [call('path/to/source', 'path/to/target')]
    assert dlj.output == ()
    assert dlj.errors == ()
    assert dlj.raised is None
    assert dlj._links_created == {'path/to/target': 'path/to/source'}


def test_DownloadLocationJob_remove_link_that_was_not_created(mocker):
    exists_mock = mocker.patch('os.path.exists')
    unlink_mock = mocker.patch('os.unlink')
    removedirs_mock = mocker.patch('os.removedirs')
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(dlj, '_links_created', {'path/to/target': 'path/to/source'})
    dlj._remove_link('path/to/different/target')
    assert exists_mock.call_args_list == []
    assert unlink_mock.call_args_list == []
    assert removedirs_mock.call_args_list == []
    assert dlj.output == ()
    assert dlj.errors == ()
    assert dlj.raised is None
    assert dlj._links_created == {'path/to/target': 'path/to/source'}

def test_DownloadLocationJob_remove_link_that_does_not_exist(mocker):
    exists_mock = mocker.patch('os.path.exists', return_value=False)
    unlink_mock = mocker.patch('os.unlink')
    removedirs_mock = mocker.patch('os.removedirs')
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(dlj, '_links_created', {
        'path/to/a': 'path/to/a1',
        'path/to/b': 'path/to/b1',
        'path/to/c': 'path/to/c1',
    })
    dlj._remove_link('path/to/b')
    assert exists_mock.call_args_list == [call('path/to/b')]
    assert unlink_mock.call_args_list == []
    assert removedirs_mock.call_args_list == []
    assert dlj.output == ()
    assert dlj.errors == ()
    assert dlj.raised is None
    assert dlj._links_created == {
        'path/to/a': 'path/to/a1',
        'path/to/b': 'path/to/b1',
        'path/to/c': 'path/to/c1',
    }

def test_DownloadLocationJob_remove_link_that_cannot_be_removed(mocker):
    exists_mock = mocker.patch('os.path.exists', return_value=True)
    unlink_mock = mocker.patch('os.unlink', side_effect=OSError('nope'))
    removedirs_mock = mocker.patch('os.removedirs')
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(dlj, '_links_created', {
        'path/to/a': 'path/to/a1',
        'path/to/b': 'path/to/b1',
        'path/to/c': 'path/to/c1',
    })
    dlj._remove_link('path/to/b')
    assert exists_mock.call_args_list == [call('path/to/b')]
    assert unlink_mock.call_args_list == [call('path/to/b')]
    assert removedirs_mock.call_args_list == []
    assert dlj.output == ()
    assert dlj.errors == ()
    assert type(dlj.raised) is OSError
    assert str(dlj.raised) == 'nope'
    assert dlj._links_created == {
        'path/to/a': 'path/to/a1',
        'path/to/b': 'path/to/b1',
        'path/to/c': 'path/to/c1',
    }

def test_DownloadLocationJob_remove_link_removes_link(mocker):
    exists_mock = mocker.patch('os.path.exists', return_value=True)
    unlink_mock = mocker.patch('os.unlink')
    removedirs_mock = mocker.patch('os.removedirs')
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(dlj, '_links_created', {
        'path/to/a': 'path/to/a1',
        'path/to/b': 'path/to/b1',
        'path/to/c': 'path/to/c1',
    })
    dlj._remove_link('path/to/b')
    assert exists_mock.call_args_list == [call('path/to/b')]
    assert unlink_mock.call_args_list == [call('path/to/b')]
    assert removedirs_mock.call_args_list == [call('path/to')]
    assert dlj.output == ()
    assert dlj.errors == ()
    assert dlj.raised is None
    assert dlj._links_created == {
        'path/to/a': 'path/to/a1',
        'path/to/c': 'path/to/c1',
    }

def test_DownloadLocationJob_remove_link_ignores_errors_from_removing_empty_parent_directories(mocker):
    exists_mock = mocker.patch('os.path.exists', return_value=True)
    unlink_mock = mocker.patch('os.unlink')
    removedirs_mock = mocker.patch('os.removedirs', side_effect=OSError('nope'))
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(dlj, '_links_created', {
        'path/to/a': 'path/to/a1',
        'path/to/b': 'path/to/b1',
        'path/to/c': 'path/to/c1',
    })
    dlj._remove_link('path/to/c')
    assert exists_mock.call_args_list == [call('path/to/c')]
    assert unlink_mock.call_args_list == [call('path/to/c')]
    assert removedirs_mock.call_args_list == [call('path/to')]
    assert dlj.output == ()
    assert dlj.errors == ()
    assert dlj.raised is None
    assert dlj._links_created == {
        'path/to/a': 'path/to/a1',
        'path/to/b': 'path/to/b1',
    }


def test_DownloadLocationJob_check_location(mocker):
    dlj = download_location.DownloadLocationJob(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(type(dlj), 'cache_directory', PropertyMock(return_value='mock/cache/directory'))
    mocker.patch.object(type(dlj), 'name', PropertyMock(return_value='mock_name'))
    assert dlj._check_location == 'mock/cache/directory/mock_name'


@pytest.mark.parametrize(
    argnames='input, exp_output',
    argvalues=(
        ({'a': [], 'b': [], 'c': []}, []),
        ({'a': [], 'b': [], 'c': ['c1']}, []),
        ({'a': [], 'b': ['b1'], 'c': []}, []),
        ({'a': ['a1'], 'b': [], 'c': []}, []),
        ({'a': [], 'b': ['b1'], 'c': ['c1']}, []),
        ({'a': ['a1'], 'b': ['b1'], 'c': []}, []),
        ({'a': ['a1'], 'b': [], 'c': ['c1']}, []),
        ({'a': ['a1'], 'b': ['b1'], 'c': ['c1']}, [[('a', 'a1'), ('b', 'b1'), ('c', 'c1')]]),
        (
            {'a': ['a1', 'a2'], 'b': ['b1', 'b2'], 'c': ['c1', 'c2']},
            [
                [('a', 'a1'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c2')],
                [('a', 'a1'), ('b', 'b2'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b2'), ('c', 'c2')],
                [('a', 'a2'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a2'), ('b', 'b1'), ('c', 'c2')],
                [('a', 'a2'), ('b', 'b2'), ('c', 'c1')],
                [('a', 'a2'), ('b', 'b2'), ('c', 'c2')],
            ],
        ),
        (
            {'a': ['a1', 'a2', 'a3'], 'b': ['b1'], 'c': ['c1', 'c2']},
            [
                [('a', 'a1'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c2')],
                [('a', 'a2'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a2'), ('b', 'b1'), ('c', 'c2')],
                [('a', 'a3'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a3'), ('b', 'b1'), ('c', 'c2')],
            ],
        ),
        (
            {'a': ['a1'], 'b': ['b1', 'b2', 'b3'], 'c': ['c1', 'c2', 'c3']},
            [
                [('a', 'a1'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c2')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c3')],
                [('a', 'a1'), ('b', 'b2'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b2'), ('c', 'c2')],
                [('a', 'a1'), ('b', 'b2'), ('c', 'c3')],
                [('a', 'a1'), ('b', 'b3'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b3'), ('c', 'c2')],
                [('a', 'a1'), ('b', 'b3'), ('c', 'c3')],
            ],
        ),
    ),
)
def test_Combinator(input, exp_output):
    output = list(download_location._Combinator(input))
    assert output == exp_output
