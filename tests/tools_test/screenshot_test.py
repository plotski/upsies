from unittest.mock import Mock, call, patch

import pytest

from upsies.tools import screenshot


@patch('os.path.exists')
@patch('upsies.utils.subproc.run')
def test_make_screenshot_gets_nonexisting_video_file(run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    exists_mock.return_value = False
    with pytest.raises(FileNotFoundError, match=rf'^{mock_file}: No such file or directory$'):
        screenshot.create(mock_file, 123, 'screenshot.png')
    assert exists_mock.call_args_list == [call(mock_file)]
    assert run_mock.call_args_list == []


@patch('os.path.exists', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
def test_make_screenshot_gets_invalid_timestamp(run_mock):
    mock_file = 'path/to/foo.mkv'
    with pytest.raises(ValueError, match=r"^Invalid timestamp: 'anywhere'$"):
        screenshot.create(mock_file, 'anywhere', 'screenshot.png')
    assert run_mock.call_args_list == []


@patch('os.path.exists')
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.length')
def test_make_screenshot_gets_valid_timestamp(videolength_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    videolength_mock.return_value = 1e6
    for ts in ('12', '01:24', '1:02:03', '01:02:03', '123:02:03', 123):
        exists_mock.side_effect = (True, False, True)
        screenshot.create(mock_file, ts, 'screenshot.png')
        exp_cmd = screenshot._make_ffmpeg_cmd(mock_file, ts, 'screenshot.png')
        assert run_mock.call_args_list == [call(exp_cmd,
                                                ignore_stderr=True,
                                                join_output=True)]
        run_mock.reset_mock()


@patch('os.path.exists')
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.length')
def test_make_screenshot_gets_timestamp_that_is_after_video_end(videolength_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    videolength_mock.return_value = 600

    exists_mock.side_effect = (True, False, True)
    with pytest.raises(ValueError, match=r'^Timestamp is after video end \(0:10:00\): 0:10:01$'):
        screenshot.create(mock_file, 601, 'screenshot.png')
    assert run_mock.call_args_list == []

    exists_mock.side_effect = (True, False, True)
    screenshot.create(mock_file, 599, 'screenshot.png')
    exp_cmd = screenshot._make_ffmpeg_cmd(mock_file, 599, 'screenshot.png')
    assert run_mock.call_args_list == [call(exp_cmd,
                                            ignore_stderr=True,
                                            join_output=True)]


@patch('os.path.exists')
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.length')
def test_make_screenshot_encounters_existing_screenshot_file(videolength_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    videolength_mock.return_value = 1e6
    exists_mock.side_effect = (True, True, True)
    screenshot.create(mock_file, '1:02:03', 'screenshot.png')
    assert run_mock.call_args_list == []


@patch('os.path.exists')
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.length')
def test_make_screenshot_overwrites_existing_screenshot_file(videolength_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    videolength_mock.return_value = 1e6
    exists_mock.side_effect = (True, True, True)
    screenshot.create(mock_file, '1:02:03', 'screenshot.png', overwrite=True)
    exp_cmd = screenshot._make_ffmpeg_cmd(mock_file, '1:02:03', 'screenshot.png')
    assert run_mock.call_args_list == [call(exp_cmd,
                                            ignore_stderr=True,
                                            join_output=True)]
