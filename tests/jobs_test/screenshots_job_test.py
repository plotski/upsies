import asyncio
import multiprocessing
import os
from unittest.mock import Mock, call, patch

try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock(Mock):
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)

import pytest

from upsies import errors
from upsies.jobs._common import DaemonProcess
from upsies.jobs.screenshots import (ScreenshotsJob, _screenshot_process,
                                     _screenshot_timestamps, _UploadThread)


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


def test_UploadThread_creates_Uploader_instance_after_starting(tmp_path):
    imghost_mock = Mock()
    url_callback = Mock()
    error_callback = Mock()
    finished_callback = Mock()
    uploader = _UploadThread(
        homedir=tmp_path,
        imghost=imghost_mock,
        force=False,
        url_callback=url_callback,
        error_callback=error_callback,
        finished_callback=finished_callback,
    )
    assert imghost_mock.Uploader.call_args_list == []
    uploader.start()
    assert imghost_mock.Uploader.call_args_list == [call(cache_dir=tmp_path)]

@pytest.mark.asyncio
async def test_UploadThread_with_successful_upload(tmp_path):
    imghost_mock = Mock()
    imghost_mock.Uploader().upload.side_effect = ('http://foo.jpg', 'http://baz.png')
    url_callback = Mock()
    error_callback = Mock()
    finished_callback = Mock()
    uploader = _UploadThread(
        homedir=tmp_path,
        imghost=imghost_mock,
        force=False,
        url_callback=url_callback,
        error_callback=error_callback,
        finished_callback=finished_callback,
    )
    uploader.start()
    uploader.upload('foo.jpg')
    uploader.upload('baz.png')
    uploader.finish()
    await uploader.join()
    assert url_callback.call_args_list == [call('http://foo.jpg'), call('http://baz.png')]
    assert finished_callback.call_args_list == [call()]
    assert error_callback.call_args_list == []

@pytest.mark.asyncio
async def test_UploadThread_with_failed_upload(tmp_path):
    imghost_mock = Mock()
    imghost_mock.Uploader().upload.side_effect = ('http://foo.jpg', errors.RequestError('The Error'))
    url_callback = Mock()
    error_callback = Mock()
    finished_callback = Mock()
    uploader = _UploadThread(
        homedir=tmp_path,
        imghost=imghost_mock,
        force=False,
        url_callback=url_callback,
        error_callback=error_callback,
        finished_callback=finished_callback,
    )
    uploader.start()
    uploader.upload('foo.jpg')
    uploader.upload('baz.png')
    uploader.finish()
    await uploader.join()
    assert url_callback.call_args_list == [call('http://foo.jpg')]
    assert finished_callback.call_args_list == [call()]
    assert len(error_callback.call_args_list[0][0]) == 1  # positional args
    assert len(error_callback.call_args_list[0][1]) == 0  # keyword args
    assert isinstance(error_callback.call_args_list[0][0][0], errors.RequestError)
    assert str(error_callback.call_args_list[0][0][0]) == 'The Error'

@pytest.mark.asyncio
async def test_UploadThread_passes_force_argument_to_upload_call(tmp_path):
    imghost_mock = Mock()
    imghost_mock.Uploader().upload.side_effect = ('http://foo.jpg', 'http://baz.png')
    url_callback = Mock()
    error_callback = Mock()
    finished_callback = Mock()
    uploader = _UploadThread(
        homedir=tmp_path,
        imghost=imghost_mock,
        force='this is a boolean value',
        url_callback=url_callback,
        error_callback=error_callback,
        finished_callback=finished_callback,
    )
    uploader.start()
    uploader.upload('foo.jpg')
    uploader.upload('baz.png')
    uploader.finish()
    await uploader.join()
    assert imghost_mock.Uploader.return_value.upload.call_args_list == [
        call('foo.jpg', force='this is a boolean value'),
        call('baz.png', force='this is a boolean value'),
    ]


@patch('upsies.utils.video.length')
def test_ScreenshotsJob_cache_file_without_imghost(video_length_mock, tmp_path):
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

@patch('upsies.utils.video.length')
def test_ScreenshotsJob_cache_file_with_imghost(video_length_mock, tmp_path):
    video_length_mock.return_value = 240
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='foo.mkv',
        timestamps=(120,),
        number=2,
        upload_to='imgbox',
    )
    assert sj.cache_file == os.path.join(
        tmp_path,
        '.output',
        'screenshots.imgbox.0:02:00,0:03:00.json',
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
    assert sj.screenshots_wanted == 2
    assert sj.screenshots_created == 0
    assert sj.screenshots_uploaded == 0
    assert sj.is_uploading is False
    assert not sj.is_finished
    assert sj.output == ()

@patch('upsies.utils.video.length')
@patch('upsies.tools.imghost')
@patch('upsies.jobs.screenshots._UploadThread')
@patch('upsies.jobs._common.DaemonProcess', return_value=Mock(join=AsyncMock()))
def test_ScreenshotsJob_handles_screenshot_creation(process_mock, upthread_mock, imghost_mock, video_length_mock, tmp_path):
    video_length_mock.return_value = 240
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='foo.mkv',
        timestamps=(120,),
        number=2,
    )
    assert not sj.is_finished
    assert not sj.is_uploading
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
    assert upthread_mock.call_args_list == []
    assert upthread_mock.return_value.start.call_args_list == []
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
@patch('upsies.jobs.screenshots._UploadThread')
@patch('upsies.jobs._common.DaemonProcess', return_value=Mock(join=AsyncMock()))
def test_ScreenshotsJob_handles_errors_from_screenshot_creation(process_mock, upthread_mock, imghost_mock, video_length_mock, tmp_path):
    video_length_mock.return_value = 240
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='foo.mkv',
        timestamps=(120,),
        number=2,
    )
    assert not sj.is_finished
    assert not sj.is_uploading
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
    assert upthread_mock.call_args_list == []
    assert upthread_mock.start.call_args_list == []
    assert upthread_mock.return_value.start.call_args_list == []
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

@patch('upsies.utils.video.length')
@patch('upsies.tools.imghost')
@patch('upsies.jobs.screenshots._UploadThread', return_value=Mock(join=AsyncMock()))
@patch('upsies.jobs._common.DaemonProcess', return_value=Mock(join=AsyncMock()))
def test_ScreenshotsJob_handles_screenshots_uploaded(process_mock, upthread_mock, imghost_mock, video_length_mock, tmp_path):
    video_length_mock.return_value = 240
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='foo.mkv',
        timestamps=(120,),
        number=2,
        upload_to='imgbox',
    )
    assert not sj.is_finished
    assert sj.is_uploading
    screenshot_path_cb = Mock()
    sj.on_screenshot_path(screenshot_path_cb)
    screenshot_error_cb = Mock()
    sj.on_screenshot_error(screenshot_error_cb)
    screenshots_finished_cb = Mock()
    sj.on_screenshots_finished(screenshots_finished_cb)
    assert screenshot_path_cb.call_args_list == []
    assert screenshot_error_cb.call_args_list == []
    assert screenshots_finished_cb.call_args_list == []
    upload_url_cb = Mock()
    sj.on_upload_url(upload_url_cb)
    upload_error_cb = Mock()
    sj.on_upload_error(upload_error_cb)
    uploads_finished_cb = Mock()
    sj.on_uploads_finished(uploads_finished_cb)
    assert upload_url_cb.call_args_list == []
    assert upload_error_cb.call_args_list == []
    assert uploads_finished_cb.call_args_list == []
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
    assert upthread_mock.call_args_list == [call(
        homedir=tmp_path,
        imghost=imghost_mock.imgbox,
        force=False,
        url_callback=sj.handle_upload_url,
        error_callback=sj.handle_upload_error,
        finished_callback=sj.handle_uploads_finished,
    )]
    assert upthread_mock.return_value.start.call_args_list == [call()]
    sj.handle_screenshot_path('foo.1.png')
    assert sj.screenshots_created == 1
    assert upthread_mock.return_value.upload.call_args_list == [call('foo.1.png')]
    sj.handle_upload_url('http://foo.1.png')
    assert sj.output == ('http://foo.1.png',)
    sj.handle_screenshot_path('foo.2.png')
    assert sj.screenshots_created == 2
    assert upthread_mock.return_value.upload.call_args_list == [call('foo.1.png'), call('foo.2.png')]
    sj.handle_upload_url('http://foo.2.png')
    assert sj.output == ('http://foo.1.png', 'http://foo.2.png')
    sj.handle_screenshots_finished()
    assert not sj.is_finished
    assert upthread_mock.return_value.finish.call_args_list == [call()]
    sj.handle_uploads_finished()
    asyncio.get_event_loop().run_until_complete(sj.wait())
    assert sj.is_finished
    assert sj.output == ('http://foo.1.png', 'http://foo.2.png')
    assert sj.exit_code == 0
    assert screenshot_path_cb.call_args_list == [call('foo.1.png'), call('foo.2.png')]
    assert screenshot_error_cb.call_args_list == []
    assert screenshots_finished_cb.call_args_list == [call(('foo.1.png', 'foo.2.png'))]
    assert upload_url_cb.call_args_list == [call('http://foo.1.png'), call('http://foo.2.png')]
    assert upload_error_cb.call_args_list == []
    assert uploads_finished_cb.call_args_list == [call(('http://foo.1.png', 'http://foo.2.png'))]

@patch('upsies.utils.video.length')
@patch('upsies.tools.imghost')
@patch('upsies.jobs.screenshots._UploadThread', return_value=Mock(join=AsyncMock()))
@patch('upsies.jobs._common.DaemonProcess', return_value=Mock(join=AsyncMock()))
def test_ScreenshotsJob_handles_errors_screenshot_uploads(process_mock, upthread_mock, imghost_mock, video_length_mock, tmp_path):
    video_length_mock.return_value = 240
    sj = ScreenshotsJob(
        homedir=tmp_path,
        ignore_cache=False,
        content_path='foo.mkv',
        timestamps=(120,),
        number=2,
        upload_to='imgbox',
    )
    assert not sj.is_finished
    assert sj.is_uploading
    screenshot_path_cb = Mock()
    sj.on_screenshot_path(screenshot_path_cb)
    screenshot_error_cb = Mock()
    sj.on_screenshot_error(screenshot_error_cb)
    screenshots_finished_cb = Mock()
    sj.on_screenshots_finished(screenshots_finished_cb)
    assert screenshot_path_cb.call_args_list == []
    assert screenshot_error_cb.call_args_list == []
    assert screenshots_finished_cb.call_args_list == []
    upload_url_cb = Mock()
    sj.on_upload_url(upload_url_cb)
    upload_error_cb = Mock()
    sj.on_upload_error(upload_error_cb)
    uploads_finished_cb = Mock()
    sj.on_uploads_finished(uploads_finished_cb)
    assert upload_url_cb.call_args_list == []
    assert upload_error_cb.call_args_list == []
    assert uploads_finished_cb.call_args_list == []
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
    assert upthread_mock.call_args_list == [call(
        homedir=tmp_path,
        imghost=imghost_mock.imgbox,
        force=False,
        url_callback=sj.handle_upload_url,
        error_callback=sj.handle_upload_error,
        finished_callback=sj.handle_uploads_finished,
    )]
    assert upthread_mock.return_value.start.call_args_list == [call()]
    sj.handle_screenshot_path('foo.1.png')
    assert sj.screenshots_created == 1
    assert upthread_mock.return_value.upload.call_args_list == [call('foo.1.png')]
    sj.handle_upload_url('http://foo.1.png')
    assert sj.output == ('http://foo.1.png',)
    sj.handle_screenshot_path('foo.2.png')
    assert sj.screenshots_created == 2
    assert upthread_mock.return_value.upload.call_args_list == [call('foo.1.png'), call('foo.2.png')]
    sj.handle_upload_error('Network error')
    assert sj.output == ('http://foo.1.png',)
    sj.handle_screenshots_finished()
    assert not sj.is_finished
    assert upthread_mock.return_value.finish.call_args_list == [call()]
    sj.handle_uploads_finished()
    asyncio.get_event_loop().run_until_complete(sj.wait())
    assert sj.is_finished
    assert sj.output == ('http://foo.1.png',)
    assert sj.exit_code == 1
    assert screenshot_path_cb.call_args_list == [call('foo.1.png'), call('foo.2.png')]
    assert screenshot_error_cb.call_args_list == []
    assert screenshots_finished_cb.call_args_list == [call(('foo.1.png', 'foo.2.png'))]
    assert upload_url_cb.call_args_list == [call('http://foo.1.png')]
    assert upload_error_cb.call_args_list == [call('Network error')]
    assert uploads_finished_cb.call_args_list == [call(('http://foo.1.png',))]
