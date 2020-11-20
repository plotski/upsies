import asyncio
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.jobs.imghost import ImageHostJob


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


@pytest.fixture
async def job(tmp_path, mocker, imghost):
    job = ImageHostJob(
        homedir=tmp_path,
        ignore_cache=False,
        imghost=imghost,
        images_total=3,
    )
    assert job.images_total == 3
    yield job
    job.finish()
    await job.wait()


@pytest.fixture
def imghost():
    return Mock(upload=AsyncMock())


def test_cache_file_is_None(job):
    assert job.cache_file is None


@pytest.mark.asyncio
async def test_initialize_is_called_with_path_and_images_total(tmp_path, mocker, imghost):
    mocker.patch('upsies.jobs.imghost.ImageHostJob._upload_images', AsyncMock())
    with pytest.raises(RuntimeError, match=r'^You must not specify both "image_paths" and "images_total"\.$'):
        ImageHostJob(
            homedir=tmp_path,
            ignore_cache=False,
            imghost=imghost,
            images_total=3,
            image_paths=('foo.jpg',),
        )

@pytest.mark.asyncio
async def test_initialize_is_called_without_path_and_images_total(tmp_path, mocker, imghost):
    mocker.patch('upsies.jobs.imghost.ImageHostJob._upload_images', AsyncMock())
    job = ImageHostJob(
        homedir=tmp_path,
        ignore_cache=False,
        imghost=imghost,
    )
    assert job._images_total == 0

@pytest.mark.asyncio
async def test_initialize_fills_upload_queue_with_image_paths(tmp_path, mocker, imghost):
    mocker.patch('upsies.jobs.imghost.ImageHostJob._upload_images', AsyncMock())
    image_paths = ['foo.jpg', 'bar.jpg', 'baz.jpg']
    job = ImageHostJob(
        homedir=tmp_path,
        ignore_cache=False,
        imghost=imghost,
        image_paths=image_paths,
    )
    queued_paths = [job._image_path_queue.get_nowait() for _ in range(3)]
    assert queued_paths == image_paths
    await job.wait()

@pytest.mark.asyncio
async def test_initialize_calls_upload_images(tmp_path, mocker, imghost):
    mocker.patch(
        'upsies.jobs.imghost.ImageHostJob._upload_images',
        Mock(side_effect=RuntimeError('greetings from upload_images')),
    )
    with pytest.raises(RuntimeError, match=r'^greetings from upload_images'):
        ImageHostJob(
            homedir=tmp_path,
            ignore_cache=False,
            imghost=Mock(),
            images_total=3,
        )

@pytest.mark.asyncio
async def test_job_is_finished_when_upload_images_task_terminates(tmp_path, mocker, imghost):
    mocker.patch('upsies.jobs.imghost.ImageHostJob._upload_images', AsyncMock())
    job = ImageHostJob(
        homedir=tmp_path,
        ignore_cache=False,
        imghost=Mock(),
        images_total=3,
    )
    assert not job._upload_images_task.done()
    assert not job.is_finished
    await job.wait()
    assert job._upload_images_task.done()
    assert job.is_finished


@pytest.mark.asyncio
async def test_images_total_property(job):
    job.images_total = 5
    assert job.images_total == 5
    job.set_images_total(10)
    assert job.images_total == 10


@pytest.mark.asyncio
async def test_upload_images_returns_when_queue_is_closed(job):
    for f in ('foo.jpg', 'bar.jpg', 'baz.jpg'):
        job._enqueue(f)
    job._close_queue()
    await asyncio.sleep(0.1)
    assert job.is_finished

@pytest.mark.asyncio
async def test_upload_images_reports_to_send_and_error(job):
    job._imghost.upload.side_effect = [
        'http://foo',
        errors.RequestError('bar.jpg is bad'),
        'http://baz',
    ]
    assert job.images_uploaded == 0

    job._enqueue('foo.jpg')
    await asyncio.sleep(0.1)
    assert job.output == ('http://foo',)
    assert job.errors == ()
    assert job.images_uploaded == 1
    assert job._imghost.upload.call_args_list == [
        call('foo.jpg', force=job.ignore_cache),
    ]

    job._enqueue('bar.jpg')
    await asyncio.sleep(0.1)
    assert job.output == ('http://foo',)
    assert job.errors == (errors.RequestError('bar.jpg is bad'),)
    assert job.images_uploaded == 1
    assert job._imghost.upload.call_args_list == [
        call('foo.jpg', force=job.ignore_cache),
        call('bar.jpg', force=job.ignore_cache),
    ]

    job._enqueue('baz.jpg')
    await asyncio.sleep(0.1)
    assert job.output == ('http://foo',)
    assert job.errors == (errors.RequestError('bar.jpg is bad'),)
    assert job.images_uploaded == 1
    assert job._imghost.upload.call_args_list == [
        call('foo.jpg', force=job.ignore_cache),
        call('bar.jpg', force=job.ignore_cache),
    ]


@pytest.mark.asyncio
async def test_pipe_input(job, mocker):
    mocker.patch('upsies.jobs.imghost.ImageHostJob._enqueue', Mock())
    job.pipe_input('foo.jpg')
    assert job._enqueue.call_args_list == [call('foo.jpg')]
    job.pipe_input('bar.jpg')
    assert job._enqueue.call_args_list == [call('foo.jpg'), call('bar.jpg')]

@pytest.mark.asyncio
async def test_pipe_closed(job, mocker):
    mocker.patch('upsies.jobs.imghost.ImageHostJob._close_queue', Mock())
    job.pipe_closed()
    assert job._close_queue.call_args_list == [call()]


@pytest.mark.asyncio
async def test_finish_cancels_upload_images_task(job):
    asyncio.get_event_loop().call_later(0.1, job.finish)
    await job.wait()
    assert job._upload_images_task.done()


@pytest.mark.asyncio
async def test_wait_catches_CancelledError_from_upload_images_task(job):
    assert job.exit_code is None
    job._upload_images_task.cancel()
    await job.wait()
    assert job.exit_code == 1
    assert job.is_finished is True


@pytest.mark.asyncio
async def test_exit_code_when_all_uploads_succeed(job):
    job._imghost.upload.side_effect = [
        'http://foo',
        'http://bar',
        'http://baz',
    ]
    for _ in range(3):
        job._enqueue('foo.jpg')
        await asyncio.sleep(0.1)
        assert job.exit_code is None
    job.pipe_closed()
    await asyncio.sleep(0.1)
    assert job.exit_code == 0

@pytest.mark.asyncio
async def test_exit_code_when_one_upload_fails(job):
    job._imghost.upload.side_effect = [
        'http://foo',
        errors.RequestError('Network error'),
        'http://baz',
    ]
    for i in range(3):
        job._enqueue('foo.jpg')
        await asyncio.sleep(0.1)
        if i == 0:
            assert job.exit_code is None
        else:
            assert job.exit_code == 1
    job.pipe_closed()
    await asyncio.sleep(0.1)
    assert job.exit_code == 1
