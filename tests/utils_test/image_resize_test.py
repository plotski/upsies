import os
import pathlib
from unittest.mock import call

import pytest

from upsies import errors
from upsies.utils import image


@pytest.mark.parametrize(
    argnames='image_file, dimensions, resized_file, exp_args',
    argvalues=(
        ('a.png', '10:20', 'out.jpg',
         ('-y', '-loglevel', 'level+error', '-i', 'file:a.png', '-vf', 'scale=10:20', 'file:out.jpg')),
        ('a.png', '10:20', 'out_%f.jpg',
         ('-y', '-loglevel', 'level+error', '-i', 'file:a.png', '-vf', 'scale=10:20', 'file:out_%%f.jpg')),
    ),
    ids=lambda v: str(v),
)
def test_make_resize_cmd(image_file, dimensions, resized_file, exp_args):
    cmd = image._make_resize_cmd(image_file, dimensions, resized_file)
    assert cmd == (image._ffmpeg_executable(),) + exp_args

def test_make_resize_cmd_handles_percent_characters(mocker):
    resized_path = rf'path/to/%.png'
    cmd = image._make_resize_cmd('a.png', '10:20', resized_path)
    assert cmd == (image._ffmpeg_executable(),) + (
        '-y', '-loglevel', 'level+error', '-i', 'file:a.png', '-vf', 'scale=10:20',
        r'file:path/to/%%.png',
    )


def test_resize_with_unreadable_file(mocker):
    mocker.patch('upsies.utils.fs.assert_file_readable', side_effect=errors.ContentError('No'))
    mocker.patch('upsies.utils.subproc.run')
    with pytest.raises(errors.ImageResizeError, match=r'^No$'):
        image.resize('a.jpg', 10, 20)


def test_resize_with_invalid_width(mocker):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    mocker.patch('upsies.utils.subproc.run')
    with pytest.raises(errors.ImageResizeError, match=r'^Width must be greater than zero: -1$'):
        image.resize('a.jpg', -1, 20)

def test_resize_with_invalid_height(mocker):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    with pytest.raises(errors.ImageResizeError, match=r'^Height must be greater than zero: -1$'):
        image.resize('a.jpg', 20, -1)

@pytest.mark.parametrize('extension', ('jpg', 'png'))
@pytest.mark.parametrize('target_filename', (None, 'b'))
@pytest.mark.parametrize('target_directory', (None, 'path/to/'))
@pytest.mark.parametrize(
    argnames='width, height',
    argvalues=(
        (10, 20),
        (10, 0),
        (0, 20),
        (0, 0),
    ),
    ids=lambda v: str(v),
)
def test_resize_with_valid_dimensions(width, height, target_filename, target_directory, extension, mocker, tmp_path):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    mocker.patch('upsies.utils.fs.sanitize_path', side_effect=lambda path: path + '.sanitized')
    mocker.patch('upsies.utils.image._ffmpeg_executable', return_value='ffmpeg')

    image_file = tmp_path / f'a.{extension}'
    image_file.write_bytes(b'image data')

    if target_directory:
        target_directory = str(tmp_path / target_directory)
        exp_target_directory = target_directory
    else:
        exp_target_directory = os.path.dirname(image_file)

    if target_filename:
        exp_target_filename = target_filename
    elif width and height:
        exp_target_filename = f'a.width={width},height={height}.{extension}'
    elif width:
        exp_target_filename = f'a.width={width}.{extension}'
    elif height:
        exp_target_filename = f'a.height={height}.{extension}'
    else:
        exp_target_filename = f'a.{extension}'

    exp_target_filepath = os.path.join(exp_target_directory, exp_target_filename)

    def create_target_filepath(*_, **__):
        path = pathlib.Path(exp_target_filepath + '.sanitized')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'resized image')

    run_mock = mocker.patch('upsies.utils.subproc.run', side_effect=create_target_filepath)

    resized_file = image.resize(image_file, width, height, target_directory, target_filename)
    assert resized_file == exp_target_filepath + '.sanitized'
    assert os.path.exists(resized_file)

    if width and height:
        exp_ffmpeg_cmd = ('ffmpeg', '-y', '-loglevel', 'level+error', '-i', f'file:{image_file}',
                          '-vf', f'scale=w={width}:h={height}', f'file:{resized_file}')
    elif width:
        exp_ffmpeg_cmd = ('ffmpeg', '-y', '-loglevel', 'level+error', '-i', f'file:{image_file}',
                          '-vf', f'scale=w={width}:h=-1', f'file:{resized_file}')
    elif height:
        exp_ffmpeg_cmd = ('ffmpeg', '-y', '-loglevel', 'level+error', '-i', f'file:{image_file}',
                          '-vf', f'scale=w=-1:h={height}', f'file:{resized_file}')
    else:
        exp_ffmpeg_cmd = None
    if exp_ffmpeg_cmd:
        assert run_mock.call_args_list == [call(exp_ffmpeg_cmd, ignore_errors=True, join_stderr=True)]
    else:
        assert run_mock.call_args_list == []

def test_resize_with_same_source_and_target(mocker, tmp_path):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    mkdir_mock = mocker.patch('upsies.utils.fs.mkdir')
    run_mock = mocker.patch('upsies.utils.subproc.run')
    resized_file = image.resize('path/to/image.jpg', target_directory='path/to', target_filename='image.jpg')
    assert resized_file == 'path/to/image.jpg'
    assert mkdir_mock.call_args_list == []
    assert run_mock.call_args_list == []

def test_resize_with_uncreatable_target_directory(mocker, tmp_path):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    mocker.patch('upsies.utils.image._ffmpeg_executable', return_value='ffmpeg')
    mkdir_mock = mocker.patch('upsies.utils.fs.mkdir', side_effect=errors.ContentError('mkdir failed'))
    run_mock = mocker.patch('upsies.utils.subproc.run')
    target_directory = str(tmp_path / 'foo' / 'bar')
    with pytest.raises(errors.ImageResizeError, match=r'^mkdir failed$'):
        image.resize('image/does/not/exist.jpg', target_directory=target_directory)
    assert mkdir_mock.call_args_list == [call(target_directory)]
    assert run_mock.call_args_list == []

def test_resize_with_uncopyable_target_filepath(mocker, tmp_path):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    mocker.patch('upsies.utils.image._ffmpeg_executable', return_value='ffmpeg')
    mocker.patch('shutil.copy2', side_effect=OSError('argh'))
    mocker.patch('upsies.utils.fs.mkdir')
    run_mock = mocker.patch('upsies.utils.subproc.run')
    exp_error = 'Failed to copy image/does/not/exist.jpg to image/does/not/resized.jpg: argh'
    with pytest.raises(errors.ImageResizeError, match=rf'^{exp_error}$'):
        image.resize('image/does/not/exist.jpg', target_filename='resized.jpg')
    assert run_mock.call_args_list == []

def test_resize_with_failed_ffmpeg_command(mocker):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    mocker.patch('upsies.utils.subproc.run', return_value='The error message')
    mocker.patch('os.path.exists', return_value=False)
    mocker.patch('upsies.utils.fs.mkdir')
    with pytest.raises(errors.ImageResizeError, match=r'^Failed to resize: The error message$'):
        image.resize('a.jpg', 10, 20)
