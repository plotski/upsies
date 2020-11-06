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


projectdir_test_cases = (
    ('path/to/foo', 'foo.upsies'),
    ('path/to/foo/', 'foo.upsies'),
    ('path/to//foo/', 'foo.upsies'),
    ('path/to//foo//', 'foo.upsies'),
    (None, '.'),
)

@pytest.mark.parametrize('content_path, exp_path', projectdir_test_cases)
@patch('upsies.utils.fs.assert_dir_usable')
def test_projectdir_does_not_exist(assert_dir_usable_mock, tmp_path, content_path, exp_path):
    fs.projectdir.cache_clear()
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        path = fs.projectdir(content_path)
        assert path == exp_path
        assert os.path.exists(path)
        assert os.access(path, os.R_OK | os.W_OK | os.X_OK)
    finally:
        os.chdir(cwd)

@pytest.mark.parametrize('content_path, exp_path', projectdir_test_cases)
@patch('upsies.utils.fs.assert_dir_usable')
def test_projectdir_exists(assert_dir_usable_mock, tmp_path, content_path, exp_path):
    fs.projectdir.cache_clear()
    cwd = os.getcwd()
    os.chdir(tmp_path)
    if exp_path != '.':
        os.mkdir(exp_path)
    assert os.path.exists(tmp_path / exp_path)
    try:
        path = fs.projectdir(content_path)
        assert path == exp_path
        assert os.path.exists(path)
        assert os.access(path, os.R_OK | os.W_OK | os.X_OK)
    finally:
        os.rmdir(tmp_path / exp_path)
        os.chdir(cwd)


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


def test_file_extension():
    assert fs.file_extension('Something.x264-GRP.mkv') == 'mkv'
    assert fs.file_extension('Something.x264-GRP.mp4') == 'mp4'
    assert fs.file_extension('Something') == ''


def test_file_extension_gets_Path_object():
    assert fs.file_extension(Path('some/path') / 'to' / 'file.mkv') == 'mkv'


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
