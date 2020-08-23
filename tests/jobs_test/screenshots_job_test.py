from unittest.mock import Mock, call, patch

import pytest

from upsies.jobs._common import DaemonProcess
from upsies.jobs.screenshots import (DEFAULT_NUMBER_OF_SCREENSHOTS,
                                     ScreenshotsJob, _screenshot_timestamps)


@patch('upsies.utils.video.length')
def test_screenshot_timestamps_with_defaults(video_length_mock):
    video_length_mock.return_value = 300
    timestamps = _screenshot_timestamps('foo.mkv', (), 0)
    assert timestamps == ['0:02:30', '0:03:45']

@patch('upsies.utils.video.length')
def test_screenshot_timestamps_with_number_argument(video_length_mock):
    video_length_mock.return_value = 300
    timestamps = _screenshot_timestamps('foo.mkv', (), 1)
    assert timestamps == ['0:02:30']
    timestamps = _screenshot_timestamps('foo.mkv', (), 2)
    assert timestamps == ['0:02:30', '0:03:45']
    timestamps = _screenshot_timestamps('foo.mkv', (), 3)
    assert timestamps == ['0:01:15', '0:02:30', '0:03:45']

@patch('upsies.utils.video.length')
def test_screenshot_timestamps_with_timestamps_argument(video_length_mock):
    video_length_mock.return_value = 300
    timestamps = _screenshot_timestamps('foo.mkv', (180 - 1, 120, '0:02:30'), 0)
    assert timestamps == ['0:02:00', '0:02:30', '0:02:59']

@patch('upsies.utils.video.length')
def test_screenshot_timestamps_with_number_and_timestamps_argument(video_length_mock):
    video_length_mock.return_value = 300
    timestamps = _screenshot_timestamps('foo.mkv', ('0:02:31',), 2)
    assert timestamps == ['0:01:15', '0:02:31']
    timestamps = _screenshot_timestamps('foo.mkv', ('0:02:31',), 3)
    assert timestamps == ['0:01:15', '0:02:31', '0:03:45']
    timestamps = _screenshot_timestamps('foo.mkv', ('0:02:31',), 4)
    assert timestamps == ['0:01:15', '0:01:53', '0:02:31', '0:03:45']
    timestamps = _screenshot_timestamps('foo.mkv', ('0:00:00', '0:05:00'), 4)
    assert timestamps == ['0:00:00', '0:02:30', '0:03:45', '0:05:00']
    timestamps = _screenshot_timestamps('foo.mkv', ('0:00:00', '0:05:00'), 5)
    assert timestamps == ['0:00:00', '0:01:15', '0:02:30', '0:03:45', '0:05:00']

@patch('upsies.utils.video.length')
def test_screenshot_timestamps_with_invalid_timestamp(video_length_mock):
    video_length_mock.return_value = 300
    with pytest.raises(ValueError, match=r'^Invalid timestamp: \'foo\'$'):
        _screenshot_timestamps('foo.mkv', ('0:02:00', 'foo', 240), 3)

@patch('upsies.utils.video.length')
def test_screenshot_timestamps_with_indeterminable_video_length(video_length_mock):
    video_length_mock.side_effect = ValueError('Not a video file')
    with pytest.raises(ValueError, match=r'^Not a video file$'):
        _screenshot_timestamps('foo.mkv', ('0:02:00', 240), 3)

@patch('upsies.utils.video.length')
def test_screenshot_timestamps_with_given_timestamp_out_of_bounds(video_length_mock):
    video_length_mock.return_value = 300
    timestamps = _screenshot_timestamps('foo.mkv', (3000,), 3)
    assert timestamps == ['0:02:30', '0:03:45', '0:05:00']
