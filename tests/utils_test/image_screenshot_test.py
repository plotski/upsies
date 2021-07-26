import os
import re
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.utils import image, video


@pytest.mark.parametrize(
    argnames='video_file, timestamp, screenshot_file, exp_args',
    argvalues=(
        ('video.mkv', '123', 'out.png',
         ('-y', '-loglevel', 'level+error', '-ss', '123', '-i', 'video.mkv',
          '-vframes', '1', '-vf', 'scale=trunc(ih*dar):ih,setsar=1/1', 'file:out.png')),
        ('video.mkv', '123', '100%.png',
         ('-y', '-loglevel', 'level+error', '-ss', '123', '-i', 'video.mkv',
          '-vframes', '1', '-vf', 'scale=trunc(ih*dar):ih,setsar=1/1', 'file:100%%.png')),
    ),
    ids=lambda v: str(v),
)
def test_make_screenshot_cmd(video_file, timestamp, screenshot_file, exp_args):
    cmd = image._make_screenshot_cmd(video_file, timestamp, screenshot_file)
    assert cmd == (image._ffmpeg_executable(),) + exp_args

def test_make_screenshot_cmd_sanitizes_path(mocker):
    def sanitize_path(path):
        for c in (os.sep, '\\', '?', '<', '>', ':'):
            path = path.replace(c, '_')
        return path

    screenshot_path = rf'path{os.sep}with:some\potentially?illegal<characters>.100%.png'
    mocker.patch('upsies.utils.fs.sanitize_path', side_effect=sanitize_path)
    cmd = image._make_screenshot_cmd('video.mkv', 123, screenshot_path)
    assert cmd == (image._ffmpeg_executable(),) + (
        '-y', '-loglevel', 'level+error', '-ss', '123', '-i', 'video.mkv',
        '-vframes', '1', '-vf', 'scale=trunc(ih*dar):ih,setsar=1/1',
        rf'file:path_with_some_potentially_illegal_characters_.100%%.png',
    )


@patch('upsies.utils.fs.assert_file_readable')
@patch('upsies.utils.subproc.run')
def test_nonexisting_video_file(run_mock, assert_file_readable_mock):
    mock_file = 'path/to/foo.mkv'
    assert_file_readable_mock.side_effect = errors.ContentError('Foo you')
    with pytest.raises(errors.ScreenshotError, match=r'^Foo you$'):
        image.screenshot(mock_file, 123, 'image.png')
    assert assert_file_readable_mock.call_args_list == [call(mock_file)]
    assert run_mock.call_args_list == []


@pytest.mark.parametrize('invalid_timestamp', ('anywhere', [1, 2, 3]))
@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
def test_invalid_timestamp(run_mock, invalid_timestamp):
    mock_file = 'path/to/foo.mkv'
    with pytest.raises(errors.ScreenshotError, match=rf"^Invalid timestamp: {re.escape(repr(invalid_timestamp))}$"):
        image.screenshot(mock_file, invalid_timestamp, 'image.png')
    assert run_mock.call_args_list == []


@patch('os.path.exists')
@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.duration')
def test_valid_timestamp(duration_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    duration_mock.return_value = 1e6
    for ts in ('12', '01:24', '1:02:03', '01:02:03', '123:02:03', 123):
        exists_mock.side_effect = (False, True)
        screenshot_path = image.screenshot(mock_file, ts, 'image.png')
        assert screenshot_path == 'image.png'
        exp_cmd = image._make_screenshot_cmd(mock_file, ts, 'image.png')
        assert run_mock.call_args_list == [call(exp_cmd,
                                                ignore_errors=True,
                                                join_stderr=True)]
        run_mock.reset_mock()


@patch('os.path.exists')
@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.duration')
def test_timestamp_after_video_end(duration_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    duration_mock.return_value = 600

    exists_mock.side_effect = (False, True)
    with pytest.raises(errors.ScreenshotError, match=r'^Timestamp is after video end \(0:10:00\): 0:10:01$'):
        image.screenshot(mock_file, 601, 'image.png')
    assert run_mock.call_args_list == []

    exists_mock.side_effect = (False, True)
    screenshot_path = image.screenshot(mock_file, 599, 'image.png')
    assert screenshot_path == 'image.png'
    exp_cmd = image._make_screenshot_cmd(mock_file, 599, 'image.png')
    assert run_mock.call_args_list == [call(exp_cmd,
                                            ignore_errors=True,
                                            join_stderr=True)]


@patch('os.path.exists')
@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.duration')
def test_getting_duration_fails(duration_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    duration_mock.side_effect = errors.ContentError('not a video file')
    exists_mock.side_effect = (False, True)
    with pytest.raises(errors.ScreenshotError, match=r'^not a video file$'):
        image.screenshot(mock_file, 123, 'image.png')
    assert run_mock.call_args_list == []


@patch('os.path.exists')
@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.duration')
def test_existing_screenshot_file(duration_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    duration_mock.return_value = 1e6
    exists_mock.side_effect = (True, True)
    screenshot_path = image.screenshot(mock_file, '1:02:03', 'image.png')
    assert screenshot_path == 'image.png'
    assert run_mock.call_args_list == []


@patch('os.path.exists')
@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.duration')
def test_overwrite_existing_screenshot_file(duration_mock, run_mock, exists_mock):
    mock_file = 'path/to/foo.mkv'
    duration_mock.return_value = 1e6
    exists_mock.side_effect = (True, True)
    screenshot_path = image.screenshot(mock_file, '1:02:03', 'image.png', overwrite=True)
    assert screenshot_path == 'image.png'
    exp_cmd = image._make_screenshot_cmd(mock_file, '1:02:03', 'image.png')
    assert run_mock.call_args_list == [call(exp_cmd,
                                            ignore_errors=True,
                                            join_stderr=True)]


@patch('os.path.exists')
@patch('upsies.utils.fs.assert_file_readable', Mock(return_value=True))
@patch('upsies.utils.subproc.run')
@patch('upsies.utils.video.make_ffmpeg_input', Mock(side_effect=lambda f: f))
@patch('upsies.utils.video.duration')
def test_screenshot_file_does_not_exist_for_some_reason(duration_mock, run_mock, exists_mock):
    run_mock.return_value = 'Command error'
    mock_file = 'path/to/foo.mkv'
    duration_mock.return_value = 1e6
    exists_mock.side_effect = (False, False)
    with pytest.raises(errors.ScreenshotError, match=r'^path/to/foo.mkv: Failed to create screenshot at 601: Command error$'):
        image.screenshot(mock_file, 601, 'image.png')


def test_screenshot_has_display_aspect_ratio(data_dir, tmp_path):
    video_file = os.path.join(data_dir, 'video', 'aspect_ratio.mkv')
    screenshot_file = tmp_path / 'image.jpg'
    screenshot_path = image.screenshot(video_file, 0, screenshot_file)
    assert screenshot_path == screenshot_file
    tracks = video._tracks(screenshot_file)
    width = int(tracks['Image'][0]['Width'])
    height = int(tracks['Image'][0]['Height'])
    assert 1279 <= width <= 1280
    assert height == 534
