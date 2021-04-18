import itertools
import os
from pathlib import Path
from unittest.mock import call, patch

import pytest

from upsies import __project_name__, errors
from upsies.utils import fs


def test_assert_file_readable_with_directory(tmp_path):
    with pytest.raises(errors.ContentError, match=rf'^{tmp_path}: Is a directory$'):
        fs.assert_file_readable(tmp_path)

def test_assert_file_readable_with_nonexisting_file(tmp_path):
    path = tmp_path / 'foo'
    with pytest.raises(errors.ContentError, match=rf'^{path}: No such file or directory$'):
        fs.assert_file_readable(path)

def test_assert_file_readable_with_unreadable_file(tmp_path):
    path = tmp_path / 'foo'
    path.write_text('bar')
    os.chmod(path, mode=0o000)
    try:
        with pytest.raises(errors.ContentError, match=rf'^{path}: Permission denied$'):
            fs.assert_file_readable(path)
    finally:
        os.chmod(path, mode=0o700)


def test_assert_dir_usable_with_file(tmp_path):
    path = tmp_path / 'foo'
    path.write_text('asdf')
    with pytest.raises(errors.ContentError, match=rf'^{path}: Not a directory$'):
        fs.assert_dir_usable(path)

def test_assert_dir_usable_with_nonexisting_directory(tmp_path):
    path = tmp_path / 'foo'
    with pytest.raises(errors.ContentError, match=rf'^{path}: Not a directory$'):
        fs.assert_dir_usable(path)

def test_assert_dir_usable_with_unreadable_directory(tmp_path):
    path = tmp_path / 'foo'
    path.mkdir()
    os.chmod(path, mode=0o333)
    try:
        with pytest.raises(errors.ContentError, match=rf'^{path}: Not readable$'):
            fs.assert_dir_usable(path)
    finally:
        os.chmod(path, mode=0o700)

def test_assert_dir_usable_with_unwritable_directory(tmp_path):
    path = tmp_path / 'foo'
    path.mkdir()
    os.chmod(path, mode=0o555)
    try:
        with pytest.raises(errors.ContentError, match=rf'^{path}: Not writable$'):
            fs.assert_dir_usable(path)
    finally:
        os.chmod(path, mode=0o700)

def test_assert_dir_usable_with_unexecutable_directory(tmp_path):
    path = tmp_path / 'foo'
    path.mkdir()
    os.chmod(path, mode=0o666)
    try:
        with pytest.raises(errors.ContentError, match=rf'^{path}: Not executable$'):
            fs.assert_dir_usable(path)
    finally:
        os.chmod(path, mode=0o700)


@patch('upsies.utils.fs.assert_dir_usable')
@patch('tempfile.mkdtemp')
def test_tmpdir_creates_our_temporary_directory(mkdtemp_mock, assert_dir_usable_mock, tmp_path):
    fs.tmpdir.cache_clear()
    mkdtemp_dir = tmp_path / 'undesired_directory_name'
    mkdtemp_dir.mkdir()
    mkdtemp_mock.return_value = str(mkdtemp_dir)
    dirpath = fs.tmpdir()
    assert dirpath == str(tmp_path / __project_name__)
    assert mkdtemp_mock.call_args_list == [call()]
    assert assert_dir_usable_mock.call_args_list == [call(dirpath)]

@patch('upsies.utils.fs.assert_dir_usable')
@patch('tempfile.mkdtemp')
def test_tmpdir_handles_existing_path(mkdtemp_mock, assert_dir_usable_mock, tmp_path):
    fs.tmpdir.cache_clear()
    mkdtemp_dir = tmp_path / 'undesired_directory_name'
    mkdtemp_dir.mkdir()
    existing_tmpdir = tmp_path / __project_name__
    existing_tmpdir.mkdir()
    mkdtemp_mock.return_value = str(mkdtemp_dir)
    dirpath = fs.tmpdir()
    assert dirpath == str(tmp_path / __project_name__)
    assert mkdtemp_mock.call_args_list == [call()]
    assert assert_dir_usable_mock.call_args_list == [call(dirpath)]

@patch('tempfile.mkdtemp')
def test_tmpdir_removes_redundant_temp_dir(mkdtemp_mock, tmp_path):
    fs.tmpdir.cache_clear()
    mkdtemp_dir = tmp_path / 'undesired_directory_name'
    mkdtemp_dir.mkdir()
    existing_tmpdir = tmp_path / __project_name__
    existing_tmpdir.mkdir()
    mkdtemp_mock.return_value = str(mkdtemp_dir)
    fs.tmpdir()
    assert not os.path.exists(mkdtemp_mock.return_value)


@pytest.mark.parametrize(
    argnames='content_path, base, exp_projectdir',
    argvalues=(
        ('path/to/foo', None, 'default_path/foo.upsies'),
        ('path/to//foo', None, 'default_path/foo.upsies'),
        ('path/to/foo/', None, 'default_path/foo.upsies'),
        ('path/to/foo', 'my/path', 'my/path/foo.upsies'),
        (None, None, '.'),
        (None, 'my/path', '.'),
        ('', None, '.'),
        ('', 'my/path', '.'),
    ),
)
@patch('upsies.utils.fs.mkdir')
def test_projectdir(mkdir_mock, tmp_path, mocker, content_path, base, exp_projectdir):
    mocker.patch('upsies.constants.CACHE_DIRPATH', base or 'default_path')
    fs.projectdir.cache_clear()
    path = fs.projectdir(content_path, base=base)
    assert path == exp_projectdir
    mkdir_mock.call_args_list == [call(base), call(path)]


def test_limit_directory_size(tmp_path):
    for dirname1 in ('a', 'b', 'c'):
        for dirname2 in ('d', 'e', 'f'):
            (tmp_path / dirname1 / dirname2).mkdir(parents=True)
            (tmp_path / dirname1 / dirname2 / 'y').write_text('x' * 100)
            (tmp_path / dirname1 / dirname2 / 'empty').mkdir()
        (tmp_path / dirname1 / 'z').write_text('x' * 1000)
        (tmp_path / dirname1 / 'empty').mkdir()

    atime = 0
    atime_iter = itertools.cycle((5, 10, 20, 30, 60))
    for dirname2 in ('e', 'd', 'f'):
        for dirname1 in ('b', 'a', 'c'):
            os.utime(tmp_path / dirname1 / dirname2 / 'y', (atime, atime))
            atime += next(atime_iter)
            os.utime(tmp_path / dirname1 / 'z', (atime, atime))
            atime += next(atime_iter)

    def get_files():
        return sorted(
            (
                os.path.join(dirpath, filename)
                for dirpath, dirnames, filenames in os.walk(tmp_path)
                for filename in filenames
            ),
            key=lambda filepath: os.stat(filepath).st_atime,
        )

    orig_files = get_files()

    # No pruning necessary
    fs.limit_directory_size(tmp_path, max_total_size=3900)
    assert get_files() == orig_files

    # Prune oldest file
    fs.limit_directory_size(tmp_path, max_total_size=3800)
    assert get_files() == orig_files[1:]

    # Prune multiple files
    fs.limit_directory_size(tmp_path, max_total_size=3000)
    assert get_files() == orig_files[8:]

    # Prune all files
    fs.limit_directory_size(tmp_path, max_total_size=0)
    assert get_files() == []


def test_prune_empty_directories(tmp_path):
    (tmp_path / 'foo' / 'a' / '1').mkdir(parents=True)
    (tmp_path / 'foo' / 'a' / '2').mkdir(parents=True)
    (tmp_path / 'foo' / 'b').write_text('yes, this is b')
    (tmp_path / 'bar' / 'x').mkdir(parents=True)
    (tmp_path / 'bar' / 'y' / 'z' / '1').mkdir(parents=True)
    (tmp_path / 'bar' / 'y' / 'z' / '1' / 'c').write_text('yes, this is c')
    (tmp_path / 'bar' / 'y' / 'z' / '2').mkdir(parents=True)
    (tmp_path / 'baz').mkdir(parents=True)
    fs.prune_empty_directories(tmp_path)
    assert os.path.exists(tmp_path)
    assert os.path.isdir(tmp_path)
    tree = []
    for dirpath, dirnames, filenames in os.walk(tmp_path):
        for dirname in dirnames:
            tree.append(os.path.join(dirpath, dirname))
        for filename in filenames:
            tree.append(os.path.join(dirpath, filename))
    assert sorted(tree) == [
        f'{tmp_path}/bar',
        f'{tmp_path}/bar/y',
        f'{tmp_path}/bar/y/z',
        f'{tmp_path}/bar/y/z/1',
        f'{tmp_path}/bar/y/z/1/c',
        f'{tmp_path}/foo',
        f'{tmp_path}/foo/b',
    ]

def test_prune_empty_directories_prunes_root_directory(tmp_path):
    (tmp_path / 'foo' / 'a' / '1').mkdir(parents=True)
    (tmp_path / 'foo' / 'a' / '2').mkdir(parents=True)
    (tmp_path / 'bar' / 'x').mkdir(parents=True)
    (tmp_path / 'bar' / 'y' / 'z' / '1').mkdir(parents=True)
    (tmp_path / 'bar' / 'y' / 'z' / '2').mkdir(parents=True)
    (tmp_path / 'baz').mkdir(parents=True)
    fs.prune_empty_directories(tmp_path)
    assert not os.path.exists(tmp_path)

def test_prune_empty_directories_encounters_OSError(tmp_path):
    try:
        (tmp_path / 'bar' / 'x').mkdir(parents=True)
        (tmp_path / 'foo' / 'a' / '1').mkdir(parents=True)
        (tmp_path / 'foo' / 'a' / '2').mkdir(parents=True, mode=0o000)
        (tmp_path / 'foo' / 'a' / '3').mkdir(parents=True)
        (tmp_path / 'foo' / 'b').mkdir(parents=True)
        with pytest.raises(RuntimeError, match=rf'{tmp_path}/foo/a/2: Failed to prune: Permission denied'):
            fs.prune_empty_directories(tmp_path)
        tree = []
        for dirpath, dirnames, filenames in os.walk(tmp_path):
            for dirname in dirnames:
                tree.append(os.path.join(dirpath, dirname))
            for filename in filenames:
                tree.append(os.path.join(dirpath, filename))
        assert sorted(tree) == [
            f'{tmp_path}/bar',
            f'{tmp_path}/bar/x',
            f'{tmp_path}/foo',
            f'{tmp_path}/foo/a',
            f'{tmp_path}/foo/a/1',
            f'{tmp_path}/foo/a/2',
            f'{tmp_path}/foo/b',
        ]
    finally:
        os.chmod(tmp_path / 'foo' / 'a' / '2', 0o700)


@patch('os.makedirs')
@patch('upsies.utils.fs.assert_dir_usable')
def test_mkdir(assert_dir_usable_mock, makedirs_mock):
    fs.mkdir('path/to/dir')
    makedirs_mock.call_args_list == [call('path/to/dir')]
    assert_dir_usable_mock.call_args_list == [call('path/to/dir')]

@patch('os.makedirs')
@patch('upsies.utils.fs.assert_dir_usable')
def test_mkdir_catches_makedirs_error(assert_dir_usable_mock, makedirs_mock):
    makedirs_mock.side_effect = OSError('No way')
    with pytest.raises(errors.ContentError, match=r'^path/to/dir: No way'):
        fs.mkdir('path/to/dir')
    makedirs_mock.call_args_list == [call('path/to/dir')]
    assert_dir_usable_mock.call_args_list == []


def test_basename():
    import pathlib
    assert fs.basename('a/b/c') == 'c'
    assert fs.basename('a/b/c/') == 'c'
    assert fs.basename('a/b/c///') == 'c'
    assert fs.basename('a/b/c//d/') == 'd'
    assert fs.basename(pathlib.Path('a/b/c//d/')) == 'd'


def test_dirname():
    import pathlib
    assert fs.dirname('a/b/c') == 'a/b'
    assert fs.dirname('a/b/c/') == 'a/b'
    assert fs.dirname('a/b/c///') == 'a/b'
    assert fs.dirname('a/b/c//d/') == 'a/b/c'
    assert fs.dirname(pathlib.Path('a/b/c//d/')) == 'a/b/c'


def test_file_and_parent():
    assert fs.file_and_parent('a/b/c//d') == ('d', 'c')
    assert fs.file_and_parent('a/b/c//d/') == ('d', 'c')
    assert fs.file_and_parent('d') == ('d',)


def test_sanitize_path_on_unix(mocker):
    mocker.patch('upsies.utils.fs.os_family', return_value='unix')
    assert fs.sanitize_filename('foo/bar/baz') == 'foo_bar_baz'

def test_sanitize_path_on_windows(mocker):
    mocker.patch('upsies.utils.fs.os_family', return_value='windows')
    assert fs.sanitize_filename('foo<bar>baz :a"b/c \\1|2?3*4.txt') == 'foo_bar_baz _a_b_c _1_2_3_4.txt'


def test_file_extension():
    assert fs.file_extension('Something.x264-GRP.mkv') == 'mkv'
    assert fs.file_extension('Something.x264-GRP.mp4') == 'mp4'
    assert fs.file_extension('Something') == ''
    assert fs.file_extension(Path('some/path') / 'to' / 'file.mkv') == 'mkv'

def test_strip_extension():
    assert fs.strip_extension('Something.x264-GRP.mkv') == 'Something.x264-GRP'
    assert fs.strip_extension('Something x264-GRP.mp4') == 'Something x264-GRP'
    assert fs.strip_extension('Something x264-GRP') == 'Something x264-GRP'
    assert fs.strip_extension('Something.x264-GRP') == 'Something.x264-GRP'
    assert fs.strip_extension(Path('some/path') / 'to' / 'file.mkv') == 'some/path/to/file'
    assert fs.strip_extension('Something x264-GRP.mp4', only=('mkv', 'mp4')) == 'Something x264-GRP'
    assert fs.strip_extension('Something x264-GRP.mp4', only=('mkv', 'mp3')) == 'Something x264-GRP.mp4'


def test_file_size_of_file(tmp_path):
    filepath = tmp_path / 'file'
    filepath.write_bytes(b'foo')
    assert fs.file_size(filepath) == 3

def test_file_size_of_directory(tmp_path):
    assert fs.file_size(tmp_path) is None

def test_file_size_of_unaccessible_file(tmp_path):
    filepath = tmp_path / 'file'
    filepath.write_bytes(b'foo')
    os.chmod(tmp_path, 0o000)
    try:
        assert fs.file_size(filepath) is None
    finally:
        os.chmod(tmp_path, 0o700)

def test_file_size_of_nonexisting_file():
    assert fs.file_size('path/to/nothing') is None


def test_file_list_recurses_into_subdirectories(tmp_path):
    (tmp_path / 'a.txt').write_bytes(b'foo')
    (tmp_path / 'a').mkdir()
    (tmp_path / 'a' / 'b.txt').write_bytes(b'foo')
    (tmp_path / 'a' / 'b').mkdir()
    (tmp_path / 'a' / 'b' / 'b.txt').write_bytes(b'foo')
    (tmp_path / 'a' / 'b' / 'c').mkdir()
    (tmp_path / 'a' / 'b' / 'c' / 'c.txt').write_bytes(b'foo')
    assert fs.file_list(tmp_path) == (
        str((tmp_path / 'a.txt')),
        str((tmp_path / 'a' / 'b.txt')),
        str((tmp_path / 'a' / 'b' / 'b.txt')),
        str((tmp_path / 'a' / 'b' / 'c' / 'c.txt')),
    )

def test_file_list_sorts_files_naturally(tmp_path):
    (tmp_path / '3' / '500').mkdir(parents=True)
    (tmp_path / '3' / '500' / '1000.txt').write_bytes(b'foo')
    (tmp_path / '20').mkdir()
    (tmp_path / '20' / '9.txt').write_bytes(b'foo')
    (tmp_path / '20' / '10.txt').write_bytes(b'foo')
    (tmp_path / '20' / '99').mkdir()
    (tmp_path / '20' / '99' / '4.txt').write_bytes(b'foo')
    (tmp_path / '20' / '99' / '0001000.txt').write_bytes(b'foo')
    (tmp_path / '20' / '100').mkdir()
    (tmp_path / '20' / '100' / '7.txt').write_bytes(b'foo')
    (tmp_path / '20' / '100' / '300.txt').write_bytes(b'foo')
    assert fs.file_list(tmp_path) == (
        str((tmp_path / '3' / '500' / '1000.txt')),
        str((tmp_path / '20' / '9.txt')),
        str((tmp_path / '20' / '10.txt')),
        str((tmp_path / '20' / '99' / '4.txt')),
        str((tmp_path / '20' / '99' / '0001000.txt')),
        str((tmp_path / '20' / '100' / '7.txt')),
        str((tmp_path / '20' / '100' / '300.txt')),
    )

def test_file_list_filters_by_extensions(tmp_path):
    (tmp_path / 'bar.jpg').write_bytes(b'foo')
    (tmp_path / 'foo.txt').write_bytes(b'foo')
    (tmp_path / 'a').mkdir()
    (tmp_path / 'a' / 'a1.txt').write_bytes(b'foo')
    (tmp_path / 'a' / 'a2.jpg').write_bytes(b'foo')
    (tmp_path / 'a' / 'b').mkdir()
    (tmp_path / 'a' / 'b' / 'b1.JPG').write_bytes(b'foo')
    (tmp_path / 'a' / 'b' / 'b2.TXT').write_bytes(b'foo')
    (tmp_path / 'a' / 'b' / 'c').mkdir()
    (tmp_path / 'a' / 'b' / 'c' / 'c1.Txt').write_bytes(b'foo')
    (tmp_path / 'a' / 'b' / 'c' / 'c2.jPG').write_bytes(b'foo')
    (tmp_path / 'a' / 'b' / 'c' / 'd').mkdir()
    (tmp_path / 'a' / 'b' / 'c' / 'd' / 'd1.txt').write_bytes(b'foo')
    (tmp_path / 'a' / 'b' / 'c' / 'd' / 'd2.txt').write_bytes(b'foo')
    assert fs.file_list(tmp_path, extensions=('jpg',)) == (
        str((tmp_path / 'a' / 'a2.jpg')),
        str((tmp_path / 'a' / 'b' / 'b1.JPG')),
        str((tmp_path / 'a' / 'b' / 'c' / 'c2.jPG')),
        str((tmp_path / 'bar.jpg')),
    )
    assert fs.file_list(tmp_path, extensions=('TXT',)) == (
        str((tmp_path / 'a' / 'a1.txt')),
        str((tmp_path / 'a' / 'b' / 'b2.TXT')),
        str((tmp_path / 'a' / 'b' / 'c' / 'c1.Txt')),
        str((tmp_path / 'a' / 'b' / 'c' / 'd' / 'd1.txt')),
        str((tmp_path / 'a' / 'b' / 'c' / 'd' / 'd2.txt')),
        str((tmp_path / 'foo.txt')),
    )
    assert fs.file_list(tmp_path, extensions=('jpg', 'txt')) == (
        str((tmp_path / 'a' / 'a1.txt')),
        str((tmp_path / 'a' / 'a2.jpg')),
        str((tmp_path / 'a' / 'b' / 'b1.JPG')),
        str((tmp_path / 'a' / 'b' / 'b2.TXT')),
        str((tmp_path / 'a' / 'b' / 'c' / 'c1.Txt')),
        str((tmp_path / 'a' / 'b' / 'c' / 'c2.jPG')),
        str((tmp_path / 'a' / 'b' / 'c' / 'd' / 'd1.txt')),
        str((tmp_path / 'a' / 'b' / 'c' / 'd' / 'd2.txt')),
        str((tmp_path / 'bar.jpg')),
        str((tmp_path / 'foo.txt')),
    )

def test_file_list_if_path_is_matching_nondirectory(tmp_path):
    path = tmp_path / 'foo.txt'
    path.write_bytes(b'foo')
    assert fs.file_list(path, extensions=('txt',)) == (str(path),)

def test_file_list_if_path_is_nonmatching_nondirectory(tmp_path):
    path = tmp_path / 'foo.txt'
    path.write_bytes(b'foo')
    assert fs.file_list(path, extensions=('png',)) == ()

def test_file_list_with_unreadable_subdirectory(tmp_path):
    (tmp_path / 'foo').write_bytes(b'foo')
    (tmp_path / 'a').mkdir()
    (tmp_path / 'a' / 'a.txt').write_bytes(b'foo')
    (tmp_path / 'a' / 'b').mkdir()
    (tmp_path / 'a' / 'b' / 'b.txt').write_bytes(b'foo')
    os.chmod(tmp_path / 'a' / 'b', 0o000)
    try:
        assert fs.file_list(tmp_path) == (
            str((tmp_path / 'a' / 'a.txt')),
            str((tmp_path / 'foo')),
        )
    finally:
        os.chmod(tmp_path / 'a' / 'b', 0o700)


def test_file_tree():
    tree = (
        ('root', (
            ('sub1', (
                ('foo', 123),
                ('sub2', (
                    ('sub3', (
                        ('sub4', (
                            ('bar', 456),
                        )),
                    )),
                )),
                ('baz', 789),
            )),
        )),
    )

    assert fs.file_tree(tree) == '''
root
└─sub1
  ├─foo (123 B)
  ├─sub2
  │ └─sub3
  │   └─sub4
  │     └─bar (456 B)
  └─baz (789 B)
'''.strip()


@pytest.mark.parametrize('number', ('0', '1', '10', '11.5', '11.05', '99', '9999'))
@pytest.mark.parametrize('space', ('', ' '))
@pytest.mark.parametrize(
    argnames='prefix, multiplier',
    argvalues=(
        ('', 1),
        ('k', 1000),
        ('M', 1000**2),
        ('G', 1000**3),
        ('T', 1000**4),
        ('P', 1000**5),
        ('Ki', 1024),
        ('Mi', 1024**2),
        ('Gi', 1024**3),
        ('Ti', 1024**4),
        ('Pi', 1024**5),
    ),
)
@pytest.mark.parametrize('unit', ('', 'b', 'B'))
def test_Bytes_valid_string(number, space, prefix, multiplier, unit):
    bytes = fs.Bytes(f'{number}{space}{prefix}{unit}')
    assert bytes == int(float(number) * multiplier)

@pytest.mark.parametrize(
    argnames='string, exp_msg',
    argvalues=(
        ('foo', 'Invalid size: foo'),
        ('10x', 'Invalid unit: x'),
        ('10kx', 'Invalid unit: kx'),
        ('10 Mx', 'Invalid unit: Mx'),
    ),
)
def test_Bytes_invalid_string(string, exp_msg):
    with pytest.raises(ValueError, match=rf'^{exp_msg}$'):
        fs.Bytes(string)
