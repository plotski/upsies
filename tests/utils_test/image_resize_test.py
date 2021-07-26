import os
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

def test_make_resize_cmd_sanitizes_path(mocker):
    def sanitize_path(path):
        for c in (os.sep, '\\', '?', '<', '>', ':'):
            path = path.replace(c, '_')
        return path

    resized_path = rf'path{os.sep}with:some\potentially?illegal<characters>.100%.png'
    mocker.patch('upsies.utils.fs.sanitize_path', side_effect=sanitize_path)
    cmd = image._make_resize_cmd('a.png', '10:20', resized_path)
    assert cmd == (image._ffmpeg_executable(),) + (
        '-y', '-loglevel', 'level+error', '-i', 'file:a.png', '-vf', 'scale=10:20',
        rf'file:path_with_some_potentially_illegal_characters_.100%%.png',
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
@pytest.mark.parametrize('target_file', (None, 'b'))
@pytest.mark.parametrize(
    argnames='width, height',
    argvalues=(
        (10, 20),
        (10, None),
        (None, 20),
        (None, None),
    ),
    ids=lambda v: str(v),
)
def test_resize_with_valid_dimensions(width, height, target_file, extension, mocker, tmp_path):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    mocker.patch('upsies.utils.image._ffmpeg_executable', return_value='ffmpeg')
    run_mock = mocker.patch('upsies.utils.subproc.run')
    mocker.patch('os.path.exists', return_value=True)
    image_file = tmp_path / f'a.{extension}'
    image_file.write_bytes(b'image data')
    if target_file:
        target_file = str(tmp_path / f'{target_file}.{extension}')
    resized_file = image.resize(image_file, width, height, target_file)

    assert os.path.exists(resized_file)

    if target_file:
        exp_target_file = target_file
    elif width and height:
        exp_target_file = str(tmp_path / f'a.width={width},height={height}.{extension}')
    elif width:
        exp_target_file = str(tmp_path / f'a.width={width}.{extension}')
    elif height:
        exp_target_file = str(tmp_path / f'a.height={height}.{extension}')
    else:
        exp_target_file = str(tmp_path / f'a.{extension}')
    assert resized_file == exp_target_file

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

def test_resize_with_unwritable_target_file(mocker):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    mocker.patch('upsies.utils.image._ffmpeg_executable', return_value='ffmpeg')
    run_mock = mocker.patch('upsies.utils.subproc.run')
    exp_error = 'Failed to copy image/does/not/exist.jpg to /path/does/not/exist/: No such file or directory'
    with pytest.raises(errors.ImageResizeError, match=rf'^{exp_error}$'):
        image.resize('image/does/not/exist.jpg', None, None, '/path/does/not/exist/')
    assert run_mock.call_args_list == []


def test_resize_with_failed_ffmpeg_command(mocker):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    mocker.patch('upsies.utils.subproc.run', return_value='The error message')
    mocker.patch('os.path.exists', return_value=False)
    with pytest.raises(errors.ImageResizeError, match=r'^a.jpg: Failed to resize: The error message$'):
        image.resize('a.jpg', 10, 20)
