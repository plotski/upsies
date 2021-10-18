from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.imghosts import imgbox


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_name():
    assert imgbox.ImgboxImageHost.name == 'imgbox'


@pytest.mark.asyncio
async def test_upload_image_handles_success(tmp_path, mocker):
    pyimgbox_upload_mock = mocker.patch('pyimgbox.Gallery.upload', AsyncMock(return_value=Mock(
        success=True,
        image_url='http://foo.url',
        thumbnail_url='http://foo.thumb.url',
        edit_url='http://foo.edit.url',
    )))
    imghost = imgbox.ImgboxImageHost(cache_directory=tmp_path)
    url = await imghost._upload_image('foo.png')
    assert pyimgbox_upload_mock.call_args_list == [call('foo.png')]
    assert url == 'http://foo.url'

@pytest.mark.asyncio
async def test_upload_image_handles_error(tmp_path, mocker):
    mocker.patch('pyimgbox.Gallery.upload', AsyncMock(return_value=Mock(
        success=False,
        error='Something went wrong',
    )))
    imghost = imgbox.ImgboxImageHost(cache_directory=tmp_path)
    with pytest.raises(errors.RequestError, match=r'^Something went wrong$'):
        await imghost._upload_image('foo.png')
