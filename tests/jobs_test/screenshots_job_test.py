import queue
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs.screenshots import (ScreenshotsJob, _normalize_timestamps,
                                     _screenshots_process, _shall_terminate)
from upsies.utils.daemon import MsgType

try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock(Mock):
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)


@patch('upsies.utils.video.duration')
def test_normalize_timestamps_with_defaults(duration_mock):
    duration_mock.return_value = 300
    timestamps = _normalize_timestamps('foo.mkv', (), 0)
    assert timestamps == ['0:02:30', '0:03:45']

@patch('upsies.utils.video.duration')
def test_normalize_timestamps_with_count_argument(duration_mock):
    duration_mock.return_value = 300
    timestamps = _normalize_timestamps('foo.mkv', (), 1)
    assert timestamps == ['0:02:30']
    timestamps = _normalize_timestamps('foo.mkv', (), 2)
    assert timestamps == ['0:02:30', '0:03:45']
    timestamps = _normalize_timestamps('foo.mkv', (), 3)
    assert timestamps == ['0:01:15', '0:02:30', '0:03:45']

@patch('upsies.utils.video.duration')
def test_normalize_timestamps_with_timestamps_argument(duration_mock):
    duration_mock.return_value = 300
    timestamps = _normalize_timestamps('foo.mkv', (180 - 1, 120, '0:02:30'), 0)
    assert timestamps == ['0:02:00', '0:02:30', '0:02:59']

@patch('upsies.utils.video.duration')
def test_normalize_timestamps_with_count_and_timestamps_argument(duration_mock):
    duration_mock.return_value = 300
    timestamps = _normalize_timestamps('foo.mkv', ('0:02:31',), 2)
    assert timestamps == ['0:01:15', '0:02:31']
    timestamps = _normalize_timestamps('foo.mkv', ('0:02:31',), 3)
    assert timestamps == ['0:01:15', '0:02:31', '0:03:45']
    timestamps = _normalize_timestamps('foo.mkv', ('0:02:31',), 4)
    assert timestamps == ['0:01:15', '0:01:53', '0:02:31', '0:03:45']
    timestamps = _normalize_timestamps('foo.mkv', ('0:00:00', '0:05:00'), 4)
    assert timestamps == ['0:00:00', '0:02:30', '0:03:45', '0:05:00']
    timestamps = _normalize_timestamps('foo.mkv', ('0:00:00', '0:05:00'), 5)
    assert timestamps == ['0:00:00', '0:01:15', '0:02:30', '0:03:45', '0:05:00']

@patch('upsies.utils.video.duration')
def test_normalize_timestamps_with_invalid_timestamp(duration_mock):
    duration_mock.return_value = 300
    with pytest.raises(ValueError, match=r'^Invalid timestamp: \'foo\'$'):
        _normalize_timestamps('foo.mkv', ('0:02:00', 'foo', 240), 3)

@patch('upsies.utils.video.duration')
def test_normalize_timestamps_with_indeterminable_video_length(duration_mock):
    duration_mock.side_effect = ValueError('Not a video file')
    with pytest.raises(ValueError, match=r'^Not a video file$'):
        _normalize_timestamps('foo.mkv', ('0:02:00', 240), 3)

@patch('upsies.utils.video.duration')
def test_normalize_timestamps_with_given_timestamp_out_of_bounds(duration_mock):
    duration_mock.return_value = 300
    timestamps = _normalize_timestamps('foo.mkv', (3000,), 3)
    assert timestamps == ['0:02:30', '0:03:45', '0:05:00']


@pytest.fixture
def screenshots_process_patches(mocker):
    parent = Mock(
        first_video=Mock(return_value='path/to/video.mp4'),
        shall_terminate=Mock(return_value=False),
        normalize_timestamps=Mock(return_value=('01:00', '01:00:00')),
        screenshot=Mock(return_value='path/to/screenshot.png'),
        output_queue=Mock(),
        input_queue=Mock(),
    )
    mocker.patch('upsies.utils.video.first_video', parent.first_video)
    mocker.patch('upsies.jobs.screenshots._shall_terminate', parent.shall_terminate)
    mocker.patch('upsies.jobs.screenshots._normalize_timestamps', parent.normalize_timestamps)
    mocker.patch('upsies.utils.image.screenshot', parent.screenshot)
    yield parent

def test_screenshots_process_fails_to_find_first_video(tmp_path, screenshots_process_patches):
    screenshots_process_patches.first_video.side_effect = errors.ContentError('No video found')
    _screenshots_process(
        output_queue=screenshots_process_patches.output_queue,
        input_queue=screenshots_process_patches.input_queue,
        content_path='path/to/foo',
        timestamps=(10 * 60, '20:00'),
        count=2,
        output_dir='path/to/destination',
        overwrite=False,
    )
    assert screenshots_process_patches.mock_calls == [
        call.first_video('path/to/foo'),
        call.output_queue.put((MsgType.error, 'No video found')),
    ]

def test_screenshots_process_is_cancelled_after_finding_first_video(tmp_path, screenshots_process_patches):
    screenshots_process_patches.first_video.return_value = 'path/to/foo/bar.mkv'
    screenshots_process_patches.shall_terminate.return_value = True
    _screenshots_process(
        output_queue=screenshots_process_patches.output_queue,
        input_queue=screenshots_process_patches.input_queue,
        content_path='path/to/foo',
        timestamps=(10 * 60, '20:00'),
        count=2,
        output_dir='path/to/destination',
        overwrite=False,
    )
    assert screenshots_process_patches.mock_calls == [
        call.first_video('path/to/foo'),
        call.shall_terminate(screenshots_process_patches.input_queue),
    ]

def test_screenshots_process_fails_to_normalize_timestamps(tmp_path, screenshots_process_patches):
    screenshots_process_patches.first_video.return_value = 'path/to/foo/bar.mkv'
    screenshots_process_patches.normalize_timestamps.side_effect = ValueError('Invalid timestamp')
    _screenshots_process(
        output_queue=screenshots_process_patches.output_queue,
        input_queue=screenshots_process_patches.input_queue,
        content_path='path/to/foo',
        timestamps=(10 * 60, '20:00'),
        count=2,
        output_dir='path/to/destination',
        overwrite=False,
    )
    assert screenshots_process_patches.mock_calls == [
        call.first_video('path/to/foo'),
        call.shall_terminate(screenshots_process_patches.input_queue),
        call.output_queue.put((MsgType.info, ('video_file', 'path/to/foo/bar.mkv'))),
        call.normalize_timestamps(
            video_file='path/to/foo/bar.mkv',
            timestamps=(10 * 60, '20:00'),
            count=2,
        ),
        call.output_queue.put((MsgType.error, 'Invalid timestamp')),
    ]

def test_screenshots_process_is_cancelled_after_normalizing_timestamps(tmp_path, screenshots_process_patches):
    screenshots_process_patches.first_video.return_value = 'path/to/foo/bar.mkv'
    screenshots_process_patches.normalize_timestamps.return_value = ('0:10:00', '0:20:00')
    screenshots_process_patches.shall_terminate.side_effect = (False, True)
    _screenshots_process(
        output_queue=screenshots_process_patches.output_queue,
        input_queue=screenshots_process_patches.input_queue,
        content_path='path/to/foo',
        timestamps=(10 * 60, '20:00'),
        count=2,
        output_dir='path/to/destination',
        overwrite=False,
    )
    assert screenshots_process_patches.mock_calls == [
        call.first_video('path/to/foo'),
        call.shall_terminate(screenshots_process_patches.input_queue),
        call.output_queue.put((MsgType.info, ('video_file', 'path/to/foo/bar.mkv'))),
        call.normalize_timestamps(
            video_file='path/to/foo/bar.mkv',
            timestamps=(10 * 60, '20:00'),
            count=2,
        ),
        call.output_queue.put((MsgType.info, ('timestamps', ('0:10:00', '0:20:00')))),
        call.shall_terminate(screenshots_process_patches.input_queue),
    ]

def test_screenshots_process_is_cancelled_after_first_screenshot(tmp_path, screenshots_process_patches):
    screenshots_process_patches.first_video.return_value = 'path/to/foo/bar.mkv'
    screenshots_process_patches.normalize_timestamps.return_value = ('0:10:00', '0:20:00')
    screenshots_process_patches.shall_terminate.side_effect = (False, False, True)
    _screenshots_process(
        output_queue=screenshots_process_patches.output_queue,
        input_queue=screenshots_process_patches.input_queue,
        content_path='path/to/foo',
        timestamps=(10 * 60, '20:00'),
        count=2,
        output_dir='path/to/destination',
        overwrite=False,
    )
    assert screenshots_process_patches.mock_calls == [
        call.first_video('path/to/foo'),
        call.shall_terminate(screenshots_process_patches.input_queue),
        call.output_queue.put((MsgType.info, ('video_file', 'path/to/foo/bar.mkv'))),
        call.normalize_timestamps(
            video_file='path/to/foo/bar.mkv',
            timestamps=(10 * 60, '20:00'),
            count=2,
        ),
        call.output_queue.put((MsgType.info, ('timestamps', ('0:10:00', '0:20:00')))),
        call.shall_terminate(screenshots_process_patches.input_queue),
        call.screenshot(
            video_file='path/to/foo/bar.mkv',
            screenshot_file='path/to/destination/bar.mkv.0:10:00.png',
            timestamp='0:10:00',
            overwrite=False,
        ),
        call.output_queue.put((MsgType.info, ('screenshot', screenshots_process_patches.screenshot.return_value))),
        call.shall_terminate(screenshots_process_patches.input_queue),
    ]

def test_screenshots_process_fails_to_create_second_screenshot(tmp_path, screenshots_process_patches):
    screenshots_process_patches.first_video.return_value = 'path/to/foo/bar.mkv'
    screenshots_process_patches.normalize_timestamps.return_value = ('0:10:00', '0:20:00')
    screenshots_process_patches.screenshot.side_effect = (
        'path/to/destination/bar.mkv.0:10:00.png',
        errors.ScreenshotError('No space left'),
    )
    _screenshots_process(
        output_queue=screenshots_process_patches.output_queue,
        input_queue=screenshots_process_patches.input_queue,
        content_path='path/to/foo',
        timestamps=(10 * 60, '20:00'),
        count=2,
        output_dir='path/to/destination',
        overwrite=False,
    )
    assert screenshots_process_patches.mock_calls == [
        call.first_video('path/to/foo'),
        call.shall_terminate(screenshots_process_patches.input_queue),
        call.output_queue.put((MsgType.info, ('video_file', 'path/to/foo/bar.mkv'))),
        call.normalize_timestamps(
            video_file='path/to/foo/bar.mkv',
            timestamps=(10 * 60, '20:00'),
            count=2,
        ),
        call.output_queue.put((MsgType.info, ('timestamps', ('0:10:00', '0:20:00')))),
        call.shall_terminate(screenshots_process_patches.input_queue),
        call.screenshot(
            video_file='path/to/foo/bar.mkv',
            screenshot_file='path/to/destination/bar.mkv.0:10:00.png',
            timestamp='0:10:00',
            overwrite=False,
        ),
        call.output_queue.put((MsgType.info, ('screenshot', 'path/to/destination/bar.mkv.0:10:00.png'))),
        call.shall_terminate(screenshots_process_patches.input_queue),
        call.screenshot(
            video_file='path/to/foo/bar.mkv',
            screenshot_file='path/to/destination/bar.mkv.0:20:00.png',
            timestamp='0:20:00',
            overwrite=False,
        ),
        call.output_queue.put((MsgType.error, 'No space left')),
    ]

def test_screenshots_process_succeeds(tmp_path, screenshots_process_patches):
    screenshots_process_patches.first_video.return_value = 'path/to/foo/bar.mkv'
    screenshots_process_patches.normalize_timestamps.return_value = ('0:10:00', '0:20:00')
    screenshots_process_patches.screenshot.side_effect = (
        'path/to/destination/one.png',
        'path/to/destination/two.png',
    )
    _screenshots_process(
        output_queue=screenshots_process_patches.output_queue,
        input_queue=screenshots_process_patches.input_queue,
        content_path='path/to/foo',
        timestamps=(10 * 60, '20:00'),
        count=2,
        output_dir='path/to/destination',
        overwrite=False,
    )
    assert screenshots_process_patches.mock_calls == [
        call.first_video('path/to/foo'),
        call.shall_terminate(screenshots_process_patches.input_queue),
        call.output_queue.put((MsgType.info, ('video_file', 'path/to/foo/bar.mkv'))),
        call.normalize_timestamps(
            video_file='path/to/foo/bar.mkv',
            timestamps=(10 * 60, '20:00'),
            count=2,
        ),
        call.output_queue.put((MsgType.info, ('timestamps', ('0:10:00', '0:20:00')))),
        call.shall_terminate(screenshots_process_patches.input_queue),
        call.screenshot(
            video_file='path/to/foo/bar.mkv',
            screenshot_file='path/to/destination/bar.mkv.0:10:00.png',
            timestamp='0:10:00',
            overwrite=False,
        ),
        call.output_queue.put((MsgType.info, ('screenshot', 'path/to/destination/one.png'))),
        call.shall_terminate(screenshots_process_patches.input_queue),
        call.screenshot(
            video_file='path/to/foo/bar.mkv',
            screenshot_file='path/to/destination/bar.mkv.0:20:00.png',
            timestamp='0:20:00',
            overwrite=False,
        ),
        call.output_queue.put((MsgType.info, ('screenshot', 'path/to/destination/two.png'))),
    ]


def test_shall_terminate_with_empty_queue():
    q = Mock()
    q.get_nowait.side_effect = queue.Empty()
    assert _shall_terminate(q) is False

def test_shall_terminate_with_irrelevant_message_type():
    q = Mock()
    q.get_nowait.return_value = ('foo', 'bar')
    assert _shall_terminate(q) is False

def test_shall_terminate_with_terminate_message():
    q = Mock()
    q.get_nowait.return_value = (MsgType.terminate, None)
    assert _shall_terminate(q) is True


@pytest.fixture
def job(tmp_path, mocker):
    DaemonProcess_mock = Mock(
        return_value=Mock(
            join=AsyncMock(),
        ),
    )
    mocker.patch('upsies.utils.daemon.DaemonProcess', DaemonProcess_mock)
    return ScreenshotsJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=False,
        content_path='some/path',
        timestamps=(120,),
        count=2,
    )


@pytest.mark.asyncio  # Ensure aioloop exists
async def test_cache_id(tmp_path):
    job = ScreenshotsJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        content_path='some/path',
    )
    assert job.cache_id is None


@patch('upsies.utils.daemon.DaemonProcess')
def test_ScreenshotsJob_initialize(DaemonProcess_mock, tmp_path):
    job = ScreenshotsJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=False,
        content_path='some/path',
        timestamps=(120,),
        count=2,
    )
    assert DaemonProcess_mock.call_args_list == [call(
        name=job.name,
        target=_screenshots_process,
        kwargs={
            'content_path' : 'some/path',
            'timestamps'   : (120,),
            'count'        : 2,
            'output_dir'   : job.home_directory,
            'overwrite'    : job.ignore_cache,
        },
        info_callback=job._handle_info,
        error_callback=job._handle_error,
        finished_callback=job.finish,
    )]
    assert job._video_file == ''
    assert job._timestamps == ()
    assert job._screenshots_process is DaemonProcess_mock.return_value
    assert job.output == ()
    assert job.errors == ()
    assert not job.is_finished
    assert job.exit_code is None
    assert job.screenshots_created == 0
    assert job.screenshots_total == -1


def test_ScreenshotsJob_execute(job, tmp_path):
    assert job._screenshots_process.start.call_args_list == []
    job.execute()
    assert job._screenshots_process.start.call_args_list == [call()]
    assert not job.is_finished
    assert job.exit_code is None


def test_ScreenshotsJob_finish(job, tmp_path):
    job.execute()
    assert job._screenshots_process.stop.call_args_list == []
    job.finish()
    assert job._screenshots_process.stop.call_args_list == [call()]


def test_ScreenshotsJob_handle_info_sets_video_file(job):
    cb = Mock()
    job.signal.register('video_file', cb)
    assert job.video_file == ''
    job._handle_info(('video_file', 'foo.mkv'))
    assert job.video_file == 'foo.mkv'
    assert cb.call_args_list == [call('foo.mkv')]

def test_ScreenshotsJob_handle_info_sets_timestamps(job):
    cb = Mock()
    job.signal.register('timestamps', cb)
    assert job.timestamps == ()
    job._handle_info(('timestamps', ('1', '2', '3')))
    assert job.timestamps == ('1', '2', '3')
    assert cb.call_args_list == [call(('1', '2', '3'))]

def test_ScreenshotsJob_handle_info_sends_screenshot_paths(job):
    assert job.output == ()
    job._handle_info(('screenshot', 'path/to/foo.png'))
    assert job.output == ('path/to/foo.png',)
    job._handle_info(('screenshot', 'path/to/bar.png'))
    assert job.output == ('path/to/foo.png', 'path/to/bar.png')
    job._handle_info(('screenshot', 'path/to/baz.png'))
    assert job.output == ('path/to/foo.png', 'path/to/bar.png', 'path/to/baz.png')


def test_ScreenshotsJob_handle_error_with_exception(job):
    assert job.raised is None
    assert job.errors == ()
    job._handle_error(errors.ScreenshotError('Foo!'))
    assert job.raised == errors.ScreenshotError('Foo!')
    assert job.errors == ()
    assert job.is_finished

def test_ScreenshotsJob_handle_error_with_string(job):
    assert job.errors == ()
    job._handle_error('Foo!')
    assert job.errors == ('Foo!',)
    assert job.is_finished


@pytest.mark.parametrize(
    argnames=('screenshots_total', 'output', 'exp_exit_code'),
    argvalues=(
        (-1, ('a.jpg', 'b.jpg', 'c.jpg'), 0),
        (-1, (), 1),
        (0, (), 0),
        (1, (), 1),
        (3, (), 1),
        (3, ('a.jpg',), 1),
        (3, ('a.jpg', 'b.jpg'), 1),
        (3, ('a.jpg', 'b.jpg', 'c.jpg'), 0),
    ),
)
@pytest.mark.asyncio
async def test_exit_code(screenshots_total, output, exp_exit_code, job):
    assert job.exit_code is None
    for o in output:
        job.send(o)
    job._screenshots_total = screenshots_total
    job.finish()
    await job.wait()
    assert job.is_finished
    assert job.exit_code == exp_exit_code


def test_video_file(job):
    assert job.video_file is job._video_file


def test_timestamps(job):
    assert job.timestamps is job._timestamps


def test_screenshots_total(job):
    assert job.screenshots_total is job._screenshots_total


def test_screenshots_created(job):
    assert job.screenshots_created is job._screenshots_created
