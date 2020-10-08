import asyncio
import multiprocessing
import os
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs.screenshots import (ScreenshotsJob, _screenshot_process,
                                     _screenshot_timestamps)
from upsies.utils.daemon import DaemonProcess

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


@pytest.fixture
def job(tmp_path):
    DaemonProcess_mock = Mock(
        return_value=Mock(
            join=AsyncMock(),
        ),
    )
    with patch('upsies.utils.daemon.DaemonProcess', DaemonProcess_mock):
        with patch('upsies.utils.video.first_video', Mock()):
            with patch('upsies.jobs.screenshots._screenshot_timestamps', Mock(return_value=(60, 120, 180))):
                return ScreenshotsJob(
                    homedir=tmp_path,
                    ignore_cache=False,
                    content_path='some/path',
                    timestamps=(120,),
                    number=2,
                )


@patch('upsies.utils.daemon.DaemonProcess', Mock())
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

@patch('upsies.utils.daemon.DaemonProcess', Mock())
@patch('upsies.utils.video.first_video')
@patch('upsies.jobs.screenshots._screenshot_timestamps', Mock(return_value=(60, 120, 180)))
def test_ScreenshotsJob_initialize_uses_first_video_file(first_video_mock, tmp_path):
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='some/path',
        timestamps=(120,),
        number=2,
    )
    assert sj._video_file == first_video_mock.return_value
    assert first_video_mock.call_args_list == [call('some/path')]

@patch('upsies.utils.daemon.DaemonProcess', Mock())
@patch('upsies.utils.video.first_video')
@patch('upsies.jobs.screenshots._screenshot_timestamps')
def test_ScreenshotsJob_initialize_gets_timestamps(screenshot_timestamps_mock, first_video_mock, tmp_path):
    screenshot_timestamps_mock.return_value = (60, 120, 180)
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='some/path',
        timestamps=(120,),
        number=2,
    )
    assert sj._timestamps == screenshot_timestamps_mock.return_value
    assert screenshot_timestamps_mock.call_args_list == [call(
        video_file=first_video_mock.return_value,
        timestamps=(120,),
        number=2,
    )]

@patch('upsies.utils.daemon.DaemonProcess', Mock())
@patch('upsies.utils.video.first_video', Mock())
@patch('upsies.jobs.screenshots._screenshot_timestamps', Mock(return_value=(60, 120, 180)))
def test_ScreenshotsJob_initialize_sets_initial_status(tmp_path):
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='some/path',
        timestamps=(120,),
        number=2,
    )
    assert sj.screenshots_created == 0
    assert sj.screenshots_total == 3

@patch('upsies.utils.daemon.DaemonProcess')
@patch('upsies.utils.video.first_video', Mock())
@patch('upsies.jobs.screenshots._screenshot_timestamps', Mock(return_value=(60, 120, 180)))
def test_ScreenshotsJob_initialize_creates_screenshot_process(DaemonProcess_mock, tmp_path):
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='some/path',
        timestamps=(120,),
        number=2,
    )
    assert DaemonProcess_mock.call_args_list == [call(
        name=sj.name,
        target=_screenshot_process,
        kwargs={
            'video_file' : sj._video_file,
            'timestamps' : sj._timestamps,
            'output_dir' : sj.homedir,
            'overwrite'  : sj.ignore_cache,
        },
        info_callback=sj.handle_screenshot,
        error_callback=sj.error,
        finished_callback=sj.finish,
    )]
    assert sj._screenshot_process is DaemonProcess_mock.return_value


def test_ScreenshotsJob_handle_screenshot(job):
    assert job.output == ()
    assert job.screenshots_created == 0

    job.handle_screenshot('foo.jpg')
    assert job.output == ('foo.jpg',)
    assert job.screenshots_created == 1

    job.handle_screenshot('bar.jpg')
    assert job.output == ('foo.jpg', 'bar.jpg')
    assert job.screenshots_created == 2


def test_ScreenshotsJob_execute(job):
    assert job.execute() is None
    assert job._screenshot_process.start.call_args_list == [call()]


def test_ScreenshotsJob_finish(job):
    assert not job.is_finished
    job.finish()
    assert job.is_finished
    assert job._screenshot_process.stop.call_args_list == [call()]


@pytest.mark.asyncio
async def test_ScreenshotsJob_wait_finishes(job):
    asyncio.get_event_loop().call_soon(job.finish)
    assert not job.is_finished
    await job.wait()
    assert job._screenshot_process.join.call_args_list == [call()]
    assert job.is_finished

@pytest.mark.asyncio
async def test_ScreenshotsJob_wait_can_be_called_multiple_times(job):
    asyncio.get_event_loop().call_soon(job.finish)
    await job.wait()
    await job.wait()


@pytest.mark.asyncio
async def test_exit_code(job):
    assert job.exit_code is None
    job.finish()
    if not job.is_finished:
        assert job.exit_code is None
    else:
        assert job.exit_code is not None
    await job.wait()
    assert job.is_finished
    job._screenshots_total = job.screenshots_created
    assert job.exit_code == 0


def test_screenshots_total(job):
    assert job.screenshots_total is job._screenshots_total


def test_screenshots_created(job):
    assert job.screenshots_created is job._screenshots_created
