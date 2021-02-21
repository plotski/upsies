from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.jobs.imghost import ImageHostJob
from upsies.utils.imghosts import ImageHostBase


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def imghost(tmp_path):
    class TestImageHost(ImageHostBase):
        name = 'testhost'
        upload = AsyncMock()
        _upload = 'not an abstract base method'
    return TestImageHost()

@pytest.fixture
async def make_ImageHostJob(tmp_path, imghost):
    def make_ImageHostJob(home_directory=tmp_path, images_total=0, enqueue=()):
        return ImageHostJob(
            home_directory=home_directory,
            ignore_cache=False,
            imghost=imghost,
            images_total=images_total,
            enqueue=enqueue,
        )
    return make_ImageHostJob


def test_cache_id(make_ImageHostJob):
    job = make_ImageHostJob(images_total=1)
    assert job.cache_id is None


def test_cache_directory_of_imghost(make_ImageHostJob, tmp_path):
    job = make_ImageHostJob()
    assert job._imghost.cache_directory is job.cache_directory
    job = make_ImageHostJob(home_directory=tmp_path)
    assert job._imghost.cache_directory is job.cache_directory


def test_initialize_is_called_with_enqueue_and_images_total(make_ImageHostJob):
    with pytest.raises(RuntimeError, match=(r'^You must not give both arguments '
                                            r'"enqueue" and "images_total"\.$')):
        make_ImageHostJob(images_total=24, enqueue=('a', 'b', 'c'))

def test_initialize_is_called_without_enqueue_and_images_total(make_ImageHostJob, mocker):
    job = make_ImageHostJob()
    assert job.images_total == 0


@pytest.mark.asyncio
async def test_initialize_is_called_with_enqueue(make_ImageHostJob, mocker):
    job = make_ImageHostJob(enqueue=('a', 'b', 'c'))
    assert job.images_total == 3
    job.execute()
    await job.wait()
    assert job.is_finished

@pytest.mark.asyncio
async def test_initialize_is_called_with_images_total(make_ImageHostJob, mocker):
    job = make_ImageHostJob(images_total=5)
    assert job.images_total == 5


def test_images_total_property(make_ImageHostJob):
    job = make_ImageHostJob(images_total=4)
    job.images_total = 4
    assert job.images_total == 4
    job.set_images_total(10)
    assert job.images_total == 10


@pytest.mark.asyncio
async def test_handle_input_sends_image_url(make_ImageHostJob):
    job = make_ImageHostJob(images_total=3)
    job._imghost.upload.side_effect = ('http://foo', 'http://bar')
    assert job.images_uploaded == 0

    await job.handle_input('foo.jpg')
    assert job._imghost.upload.call_args_list == [
        call('foo.jpg', cache=not job.ignore_cache),
    ]
    assert job.output == ('http://foo',)
    assert job.errors == ()
    assert job.images_uploaded == 1

    await job.handle_input('bar.jpg')
    assert job._imghost.upload.call_args_list == [
        call('foo.jpg', cache=not job.ignore_cache),
        call('bar.jpg', cache=not job.ignore_cache),
    ]
    assert job.output == ('http://foo', 'http://bar')
    assert job.errors == ()
    assert job.images_uploaded == 2

@pytest.mark.asyncio
async def test_handle_input_handles_RequestError(make_ImageHostJob):
    job = make_ImageHostJob(images_total=3)
    job._imghost.upload.side_effect = errors.RequestError('ugly image')
    await job.handle_input('foo.jpg')
    assert job._imghost.upload.call_args_list == [
        call('foo.jpg', cache=not job.ignore_cache),
    ]
    assert job.output == ()
    assert job.errors == (errors.RequestError('ugly image'),)
    assert job.images_uploaded == 0


@pytest.mark.asyncio
async def test_exit_code(make_ImageHostJob):
    job = make_ImageHostJob(images_total=123)
    assert job.exit_code is None
    job.execute()
    assert job.exit_code is None
    job.finish()
    await job.wait()
    assert job.exit_code is not None
    job._images_uploaded = 0
    assert job.exit_code == 1
    job._images_uploaded = 122
    assert job.exit_code == 1
    job._images_uploaded = 123
    assert job.exit_code == 0
