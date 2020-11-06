from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.tools import screenshot


@patch('upsies.utils.fs.assert_file_readable')
@patch('upsies.utils.subproc.run')
def test_nonexisting_video_file(run_mock, assert_file_readable_mock):
    mock_file = 'path/to/foo.mkv'
    assert_file_readable_mock.side_effect = errors.ContentError('Foo you')
    with pytest.raises(errors.ScreenshotError, match=r'^Foo you$'):
        screenshot.create(mock_file, 123, 'screenshot.png')
    assert assert_file_readable_mock.call_args_list == [call(mock_file)]
    assert run_mock.call_args_list == []


@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
def test_invalid_timestamp(run_mock):
    mock_file = 'path/to/foo.mkv'
    with pytest.raises(errors.ScreenshotError, match=r"^Invalid timestamp: 'anywhere'$"):
        screenshot.create(mock_file, 'anywhere', 'screenshot.png')
    assert run_mock.call_args_list == []


@patch('os.path.exists')
@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.length')
def test_valid_timestamp(videolength_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    videolength_mock.return_value = 1e6
    for ts in ('12', '01:24', '1:02:03', '01:02:03', '123:02:03', 123):
        exists_mock.side_effect = (False, True)
        screenshot.create(mock_file, ts, 'screenshot.png')
        exp_cmd = screenshot._make_ffmpeg_cmd(mock_file, ts, 'screenshot.png')
        assert run_mock.call_args_list == [call(exp_cmd,
                                                ignore_errors=True,
                                                join_stderr=True)]
        run_mock.reset_mock()


@patch('os.path.exists')
@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.length')
def test_timestamp_after_video_end(videolength_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    videolength_mock.return_value = 600

    exists_mock.side_effect = (False, True)
    with pytest.raises(errors.ScreenshotError, match=r'^Timestamp is after video end \(0:10:00\): 0:10:01$'):
        screenshot.create(mock_file, 601, 'screenshot.png')
    assert run_mock.call_args_list == []

    exists_mock.side_effect = (False, True)
    screenshot.create(mock_file, 599, 'screenshot.png')
    exp_cmd = screenshot._make_ffmpeg_cmd(mock_file, 599, 'screenshot.png')
    assert run_mock.call_args_list == [call(exp_cmd,
                                            ignore_errors=True,
                                            join_stderr=True)]


@patch('os.path.exists')
@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.length')
def test_existing_screenshot_file(videolength_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    videolength_mock.return_value = 1e6
    exists_mock.side_effect = (True, True)
    screenshot.create(mock_file, '1:02:03', 'screenshot.png')
    assert run_mock.call_args_list == []


@patch('os.path.exists')
@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.length')
def test_overwrite_existing_screenshot_file(videolength_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    videolength_mock.return_value = 1e6
    exists_mock.side_effect = (True, True)
    screenshot.create(mock_file, '1:02:03', 'screenshot.png', overwrite=True)
    exp_cmd = screenshot._make_ffmpeg_cmd(mock_file, '1:02:03', 'screenshot.png')
    assert run_mock.call_args_list == [call(exp_cmd,
                                            ignore_errors=True,
                                            join_stderr=True)]
