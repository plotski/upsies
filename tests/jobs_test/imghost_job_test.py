from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs.imghost import ImageHostJob, _UploadThread

try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock(Mock):
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)


@pytest.fixture
def job(tmp_path):
    _UploadThread_mock = Mock(
        return_value=Mock(
            join=AsyncMock(),
        ),
    )
    with patch('upsies.jobs.imghost._UploadThread', _UploadThread_mock):
        with patch('upsies.jobs.imghost.imghost'):
            return ImageHostJob(
                homedir=tmp_path,
                ignore_cache=False,
                image_host='imgfoo',
                images_total=3,
            )


def test_cache_file_is_None(job):
    assert job.cache_file is None


def test_TypeError_when_called_with_path_and_images_total(tmp_path):
    with pytest.raises(TypeError, match=r'^You must not specify both "image_paths" and "images_total"\.$'):
        ImageHostJob(
            homedir=tmp_path,
            ignore_cache=False,
            image_host='imgfoo',
            images_total=3,
            image_paths=('foo.jpg',),
        )

def test_TypeError_when_called_without_path_and_images_total(tmp_path):
    with pytest.raises(TypeError, match=r'^You must specify "image_paths" or "images_total"\.$'):
        ImageHostJob(
            homedir=tmp_path,
            ignore_cache=False,
            image_host='imgfoo',
        )

def test_ValueError_when_called_with_unknown_image_host(tmp_path):
    with pytest.raises(ValueError, match=r'^Unknown image hosting service: imgfoo$'):
        ImageHostJob(
            homedir=tmp_path,
            ignore_cache=False,
            image_host='imgfoo',
            images_total=3,
        )

@patch('upsies.jobs.imghost.imghost')
@patch('upsies.jobs.imghost._UploadThread')
def test_upload_thread_is_created_during_initialization(_UploadThread_mock, imghost_mock, tmp_path):
    job = ImageHostJob(
        homedir=tmp_path,
        ignore_cache=False,
        image_host='imgfoo',
        images_total=3,
    )
    assert job._upload_thread is _UploadThread_mock.return_value
    assert _UploadThread_mock.call_args_list == [call(
        homedir=job.homedir,
        imghost=imghost_mock.imgfoo,
        force=False,
        url_callback=job.handle_image_url,
        error_callback=job.error,
        finished_callback=job.handle_uploads_finished,
    )]

@patch('upsies.jobs.imghost.imghost', Mock())
@patch('upsies.jobs.imghost._UploadThread')
def test_upload_queue_is_filled_with_image_paths(_UploadThread_mock, tmp_path):
    job = ImageHostJob(
        homedir=tmp_path,
        ignore_cache=False,
        image_host='imgfoo',
        image_paths=('foo.jpg', 'bar.jpg', 'baz.png'),
    )
    assert job.images_total == 3
    assert _UploadThread_mock.return_value.upload.call_args_list == [
        call('foo.jpg'),
        call('bar.jpg'),
        call('baz.png'),
    ]
    assert _UploadThread_mock.return_value.finish.call_args_list == [call()]

@patch('upsies.jobs.imghost.imghost', Mock())
@patch('upsies.jobs.imghost._UploadThread')
def test_waiting_for_images_on_pipe(_UploadThread_mock, tmp_path):
    job = ImageHostJob(
        homedir=tmp_path,
        ignore_cache=False,
        image_host='imgfoo',
        images_total=2,
    )
    assert job.images_total == 2
    assert _UploadThread_mock.return_value.upload.call_args_list == []
    assert _UploadThread_mock.return_value.finish.call_args_list == []
    job.pipe_input('foo.jpg')
    assert _UploadThread_mock.return_value.upload.call_args_list == [call('foo.jpg')]
    assert _UploadThread_mock.return_value.finish.call_args_list == []
    job.pipe_input('bar.jpg')
    assert _UploadThread_mock.return_value.upload.call_args_list == [call('foo.jpg'), call('bar.jpg')]
    assert _UploadThread_mock.return_value.finish.call_args_list == []
    job.pipe_closed()
    assert _UploadThread_mock.return_value.finish.call_args_list == [call()]


def test_finish(job):
    assert job.finish() is None
    assert job._upload_thread.stop.call_args_list == [call()]
    assert not job.is_finished


def test_execute(job):
    assert job.execute() is None
    assert job._upload_thread.start.call_args_list == [call()]


@pytest.mark.asyncio
async def test_wait_finishes(job):
    assert not job.is_finished
    await job.wait()
    assert job._upload_thread.join.call_args_list == [call()]
    assert job.is_finished

@pytest.mark.asyncio
async def test_wait_can_be_called_multiple_times(job):
    assert not job.is_finished
    await job.wait()
    assert job.is_finished
    await job.wait()
    await job.wait()
    assert job.is_finished


@pytest.mark.asyncio
async def test_exit_code(job):
    assert job.exit_code is None
    job.finish()
    assert job.exit_code is None
    await job.wait()
    assert job.exit_code is not None


def test_images_uploaded(job):
    assert job.images_uploaded is job._images_uploaded

def test_images_total(job):
    assert job.images_total is job._images_total
    job.images_total = 4.5
    assert job.images_total == 4


def test_image_url_handling(job):
    cb = Mock()
    job.on_output(cb)
    assert job.images_uploaded == 0
    assert cb.call_args_list == []
    job.handle_image_url('http://foo.jpg')
    assert cb.call_args_list == [call('http://foo.jpg')]
    assert job.images_uploaded == 1
    assert job.output == ('http://foo.jpg',)
    job.handle_image_url('http://bar.jpg')
    assert cb.call_args_list == [call('http://foo.jpg'), call('http://bar.jpg')]
    assert job.images_uploaded == 2
    assert job.output == ('http://foo.jpg', 'http://bar.jpg')


def test_uploads_finished_handling(job):
    job.handle_uploads_finished()
    assert job._exit_code == 0


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
