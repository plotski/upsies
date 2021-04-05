from unittest.mock import call

import pytest

from upsies import errors
from upsies.utils import image


def test_make_resize_cmd():
    cmd = image._make_resize_cmd('a.jpg', '10:20', 'b.jpg')
    # Ignore ffmpeg executable
    assert cmd[1:] == ('-y', '-loglevel', 'level+error', '-i', 'file:a.jpg',
                       '-vf', 'scale=10:20', 'file:b.jpg')


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

@pytest.mark.parametrize(
    argnames='image_file, width, height, exp_args',
    argvalues=(
        ('a.jpg', 10, 20,
         ['-y', '-loglevel', 'level+error', '-i', 'file:a.jpg', '-vf', 'scale=w=10:h=20', 'file:a.resized.jpg']),
        ('a.jpg', 10, None,
         ['-y', '-loglevel', 'level+error', '-i', 'file:a.jpg', '-vf', 'scale=w=10:h=-1', 'file:a.resized.jpg']),
        ('a.jpg', None, 20,
         ['-y', '-loglevel', 'level+error', '-i', 'file:a.jpg', '-vf', 'scale=w=-1:h=20', 'file:a.resized.jpg']),
        ('a.jpg', None, None,
         []),
    ),
    ids=lambda v: str(v),
)
def test_resize_with_valid_dimensions(image_file, width, height, exp_args, mocker):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    mocker.patch('upsies.utils.image._ffmpeg_executable', return_value='ffmpeg')
    run_mock = mocker.patch('upsies.utils.subproc.run')
    mocker.patch('os.path.exists', return_value=True)
    resized_image = image.resize(image_file, width, height)
    if exp_args:
        assert resized_image == 'a.resized.jpg'
        exp_cmd = tuple(['ffmpeg'] + exp_args)
        assert run_mock.call_args_list == [call(exp_cmd, ignore_errors=True, join_stderr=True)]
    else:
        assert resized_image == 'a.jpg'
        assert run_mock.call_args_list == []


def test_resize_with_failed_ffmpeg_command(mocker):
    mocker.patch('upsies.utils.fs.assert_file_readable')
    mocker.patch('upsies.utils.subproc.run', return_value='The error message')
    mocker.patch('os.path.exists', return_value=False)
    with pytest.raises(errors.ImageResizeError, match=r'^a.jpg: Failed to resize: The error message$'):
        image.resize('a.jpg', 10, 20)
