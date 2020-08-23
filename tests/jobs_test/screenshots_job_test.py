import multiprocessing
import os
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs._common import DaemonProcess
from upsies.jobs.screenshots import (ScreenshotsJob, _screenshot_process,
                                     _screenshot_timestamps)


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


@patch('upsies.tools.screenshot.create')
def test_screenshot_process_fills_output_queue(screenshot_create_mock, tmp_path):
    output_queue = multiprocessing.Queue()
    input_queue = multiprocessing.Queue()
    _screenshot_process(output_queue, input_queue,
                        'foo.mkv', ('0:10:00', '0:20:00'), 'path/to/destination')
    assert screenshot_create_mock.call_args_list == [
        call('foo.mkv', '0:10:00', 'path/to/destination/foo.mkv.0:10:00.png'),
        call('foo.mkv', '0:20:00', 'path/to/destination/foo.mkv.0:20:00.png'),
    ]
    assert output_queue.get() == (DaemonProcess.INFO, 'path/to/destination/foo.mkv.0:10:00.png')
    assert output_queue.get() == (DaemonProcess.INFO, 'path/to/destination/foo.mkv.0:20:00.png')
    assert output_queue.empty()
    assert input_queue.empty()

@patch('upsies.tools.screenshot.create')
def test_screenshot_process_catches_ScreenshotErrors(screenshot_create_mock, tmp_path):
    def screenshot_create_side_effect(video_file, timestamp, screenshotfile):
        raise errors.ScreenshotError('Error', video_file, timestamp)

    screenshot_create_mock.side_effect = screenshot_create_side_effect

    output_queue = multiprocessing.Queue()
    input_queue = multiprocessing.Queue()
    _screenshot_process(output_queue, input_queue,
                        'foo.mkv', ('0:10:00', '0:20:00'), 'path/to/destination')
    assert screenshot_create_mock.call_args_list == [
        call('foo.mkv', '0:10:00', 'path/to/destination/foo.mkv.0:10:00.png'),
        call('foo.mkv', '0:20:00', 'path/to/destination/foo.mkv.0:20:00.png'),
    ]
    assert output_queue.get() == (DaemonProcess.ERROR, str(errors.ScreenshotError('Error', 'foo.mkv', '0:10:00')))
    assert output_queue.get() == (DaemonProcess.ERROR, str(errors.ScreenshotError('Error', 'foo.mkv', '0:20:00')))
    assert output_queue.empty()
    assert input_queue.empty()

@patch('upsies.tools.screenshot.create')
def test_screenshot_process_catches_ValueErrors(screenshot_create_mock, tmp_path):
    def screenshot_create_side_effect(video_file, timestamp, screenshotfile):
        raise ValueError(f'Error: {video_file}, {timestamp}')

    screenshot_create_mock.side_effect = screenshot_create_side_effect

    output_queue = multiprocessing.Queue()
    input_queue = multiprocessing.Queue()
    _screenshot_process(output_queue, input_queue,
                        'foo.mkv', ('0:10:00', '0:20:00'), 'path/to/destination')
    assert screenshot_create_mock.call_args_list == [
        call('foo.mkv', '0:10:00', 'path/to/destination/foo.mkv.0:10:00.png'),
        call('foo.mkv', '0:20:00', 'path/to/destination/foo.mkv.0:20:00.png'),
    ]
    assert output_queue.get() == (DaemonProcess.ERROR, 'Error: foo.mkv, 0:10:00')
    assert output_queue.get() == (DaemonProcess.ERROR, 'Error: foo.mkv, 0:20:00')
    assert output_queue.empty()
    assert input_queue.empty()

@patch('upsies.tools.screenshot.create')
def test_screenshot_process_does_not_catche_other_errors(screenshot_create_mock, tmp_path):
    screenshot_create_mock.side_effect = TypeError('asdf')
    output_queue = multiprocessing.Queue()
    input_queue = multiprocessing.Queue()
    with pytest.raises(TypeError, match='^asdf$'):
        _screenshot_process(output_queue, input_queue,
                            'foo.mkv', ('0:10:00', '0:20:00'), 'path/to/destination')
    assert output_queue.empty()
    assert input_queue.empty()
