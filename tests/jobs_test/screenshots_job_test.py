import asyncio
import multiprocessing
import os
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs._common import DaemonProcess
from upsies.jobs.screenshots import (ScreenshotsJob, _screenshot_process,
                                     _screenshot_timestamps)

try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock(Mock):
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)


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
                        'foo.mkv', ('0:10:00', '0:20:00'), 'path/to/destination',
                        overwrite=False)
    assert screenshot_create_mock.call_args_list == [
        call(
            video_file='foo.mkv',
            timestamp='0:10:00',
            screenshot_file='path/to/destination/foo.mkv.0:10:00.png',
            overwrite=False,
        ),
        call(
            video_file='foo.mkv',
            timestamp='0:20:00',
            screenshot_file='path/to/destination/foo.mkv.0:20:00.png',
            overwrite=False,
        ),
    ]
    assert output_queue.get() == (DaemonProcess.INFO, 'path/to/destination/foo.mkv.0:10:00.png')
    assert output_queue.get() == (DaemonProcess.INFO, 'path/to/destination/foo.mkv.0:20:00.png')
    assert output_queue.empty()
    assert input_queue.empty()

@patch('upsies.tools.screenshot.create')
def test_screenshot_process_catches_ScreenshotErrors(screenshot_create_mock, tmp_path):
    def screenshot_create_side_effect(video_file, timestamp, screenshot_file, overwrite=False):
        raise errors.ScreenshotError('Error', video_file, timestamp)

    screenshot_create_mock.side_effect = screenshot_create_side_effect

    output_queue = multiprocessing.Queue()
    input_queue = multiprocessing.Queue()
    _screenshot_process(output_queue, input_queue,
                        'foo.mkv', ('0:10:00', '0:20:00'), 'path/to/destination',
                        overwrite=False)
    assert screenshot_create_mock.call_args_list == [
        call(
            video_file='foo.mkv',
            timestamp='0:10:00',
            screenshot_file='path/to/destination/foo.mkv.0:10:00.png',
            overwrite=False,
        ),
        call(
            video_file='foo.mkv',
            timestamp='0:20:00',
            screenshot_file='path/to/destination/foo.mkv.0:20:00.png',
            overwrite=False,
        ),
    ]
    assert output_queue.get() == (DaemonProcess.ERROR, str(errors.ScreenshotError('Error', 'foo.mkv', '0:10:00')))
    assert output_queue.get() == (DaemonProcess.ERROR, str(errors.ScreenshotError('Error', 'foo.mkv', '0:20:00')))
    assert output_queue.empty()
    assert input_queue.empty()

@patch('upsies.tools.screenshot.create')
def test_screenshot_process_catches_ValueErrors(screenshot_create_mock, tmp_path):
    def screenshot_create_side_effect(video_file, timestamp, screenshot_file, overwrite=False):
        raise ValueError(f'Error: {video_file}, {timestamp}')

    screenshot_create_mock.side_effect = screenshot_create_side_effect

    output_queue = multiprocessing.Queue()
    input_queue = multiprocessing.Queue()
    _screenshot_process(output_queue, input_queue,
                        'foo.mkv', ('0:10:00', '0:20:00'), 'path/to/destination',
                        overwrite=True)
    assert screenshot_create_mock.call_args_list == [
        call(
            video_file='foo.mkv',
            timestamp='0:10:00',
            screenshot_file='path/to/destination/foo.mkv.0:10:00.png',
            overwrite=True,
        ),
        call(
            video_file='foo.mkv',
            timestamp='0:20:00',
            screenshot_file='path/to/destination/foo.mkv.0:20:00.png',
            overwrite=True,
        ),
    ]
    assert output_queue.get() == (DaemonProcess.ERROR, 'Error: foo.mkv, 0:10:00')
    assert output_queue.get() == (DaemonProcess.ERROR, 'Error: foo.mkv, 0:20:00')
    assert output_queue.empty()
    assert input_queue.empty()

@patch('upsies.tools.screenshot.create')
def test_screenshot_process_does_not_catch_other_errors(screenshot_create_mock, tmp_path):
    screenshot_create_mock.side_effect = TypeError('asdf')
    output_queue = multiprocessing.Queue()
    input_queue = multiprocessing.Queue()
    with pytest.raises(TypeError, match='^asdf$'):
        _screenshot_process(output_queue, input_queue,
                            'foo.mkv', ('0:10:00', '0:20:00'), 'path/to/destination',
                            overwrite=False)
    assert output_queue.empty()
    assert input_queue.empty()


@patch('upsies.utils.video.length')
def test_ScreenshotsJob_cache_file(video_length_mock, tmp_path):
    video_length_mock.return_value = 240
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='foo.mkv',
        timestamps=(120,),
        number=2,
    )
    assert sj.cache_file == os.path.join(
        tmp_path,
        '.output',
        'screenshots.0:02:00,0:03:00.json',
    )


@patch('upsies.tools.imghost')
@patch('upsies.utils.video.length')
def test_ScreenshotsJob_state_before_execution(video_length_mock, imghost_mock, tmp_path):
    video_length_mock.return_value = 240
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='foo.mkv',
        timestamps=(120,),
        number=2,
    )
    assert sj.exit_code is None
    assert sj.screenshots_total == 2
    assert sj.screenshots_created == 0
    assert not sj.is_finished
    assert sj.output == ()

@patch('upsies.utils.video.length')
@patch('upsies.tools.imghost')
@patch('upsies.jobs._common.DaemonProcess', return_value=Mock(join=AsyncMock()))
def test_ScreenshotsJob_handles_screenshot_creation(process_mock, imghost_mock, video_length_mock, tmp_path):
    video_length_mock.return_value = 240
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='foo.mkv',
        timestamps=(120,),
        number=2,
    )
    assert not sj.is_finished
    screenshot_path_cb = Mock()
    sj.on_screenshot_path(screenshot_path_cb)
    screenshot_error_cb = Mock()
    sj.on_screenshot_error(screenshot_error_cb)
    screenshots_finished_cb = Mock()
    sj.on_screenshots_finished(screenshots_finished_cb)
    assert screenshot_path_cb.call_args_list == []
    assert screenshot_error_cb.call_args_list == []
    assert screenshots_finished_cb.call_args_list == []
    sj.start()
    assert not sj.is_finished
    assert process_mock.call_args_list == [call(
        name=sj.name,
        target=_screenshot_process,
        kwargs={
            'video_file' : sj._video_file,
            'timestamps' : sj._timestamps,
            'output_dir' : sj.homedir,
            'overwrite'  : sj.ignore_cache,
        },
        info_callback=sj.handle_screenshot_path,
        error_callback=sj.handle_screenshot_error,
        finished_callback=sj.handle_screenshots_finished,
    )]
    assert process_mock.return_value.start.call_args_list == [call()]
    sj.handle_screenshot_path('foo.1.png')
    assert sj.screenshots_created == 1
    assert sj.output == ('foo.1.png',)
    sj.handle_screenshot_path('foo.2.png')
    assert sj.screenshots_created == 2
    assert sj.output == ('foo.1.png', 'foo.2.png')
    sj.handle_screenshots_finished()
    asyncio.get_event_loop().run_until_complete(sj.wait())
    assert sj.is_finished
    assert sj.output == ('foo.1.png', 'foo.2.png')
    assert sj.exit_code == 0
    assert screenshot_path_cb.call_args_list == [call('foo.1.png'), call('foo.2.png')]
    assert screenshot_error_cb.call_args_list == []
    assert screenshots_finished_cb.call_args_list == [call(('foo.1.png', 'foo.2.png'))]

@patch('upsies.utils.video.length')
@patch('upsies.tools.imghost')
@patch('upsies.jobs._common.DaemonProcess', return_value=Mock(join=AsyncMock()))
def test_ScreenshotsJob_handles_errors_from_screenshot_creation(process_mock, imghost_mock, video_length_mock, tmp_path):
    video_length_mock.return_value = 240
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='foo.mkv',
        timestamps=(120,),
        number=2,
    )
    assert not sj.is_finished
    screenshot_path_cb = Mock()
    sj.on_screenshot_path(screenshot_path_cb)
    screenshot_error_cb = Mock()
    sj.on_screenshot_error(screenshot_error_cb)
    screenshots_finished_cb = Mock()
    sj.on_screenshots_finished(screenshots_finished_cb)
    assert screenshot_path_cb.call_args_list == []
    assert screenshot_error_cb.call_args_list == []
    assert screenshots_finished_cb.call_args_list == []
    sj.start()
    assert not sj.is_finished
    assert process_mock.call_args_list == [call(
        name=sj.name,
        target=_screenshot_process,
        kwargs={
            'video_file' : sj._video_file,
            'timestamps' : sj._timestamps,
            'output_dir' : sj.homedir,
            'overwrite'  : sj.ignore_cache,
        },
        info_callback=sj.handle_screenshot_path,
        error_callback=sj.handle_screenshot_error,
        finished_callback=sj.handle_screenshots_finished,
    )]
    assert process_mock.return_value.start.call_args_list == [call()]
    sj.handle_screenshot_path('foo.1.png')
    assert sj.screenshots_created == 1
    assert sj.output == ('foo.1.png',)
    sj.handle_screenshot_error('Something went wrong')
    assert sj.screenshots_created == 1
    assert sj.output == ('foo.1.png',)
    sj.handle_screenshots_finished()
    asyncio.get_event_loop().run_until_complete(sj.wait())
    assert sj.is_finished
    assert sj.output == ('foo.1.png',)
    assert sj.exit_code == 1
    assert screenshot_path_cb.call_args_list == [call('foo.1.png')]
    assert screenshot_error_cb.call_args_list == [call('Something went wrong')]
    assert screenshots_finished_cb.call_args_list == [call(('foo.1.png',))]
