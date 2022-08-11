from unittest.mock import AsyncMock, Mock, call

import pytest

from upsies import errors
from upsies.utils.imghosts import imgbox


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
    pyimgbox_close_mock = mocker.patch('pyimgbox.Gallery.close', AsyncMock())
    imghost = imgbox.ImgboxImageHost(cache_directory=tmp_path)
    url = await imghost._upload_image('foo.png')
    assert pyimgbox_upload_mock.call_args_list == [call('foo.png')]
    assert pyimgbox_close_mock.call_args_list == [call()]
    assert url == 'http://foo.url'

@pytest.mark.asyncio
async def test_upload_image_handles_error(tmp_path, mocker):
    mocker.patch('pyimgbox.Gallery.upload', AsyncMock(return_value=Mock(
        success=False,
        error='Something went wrong',
    )))
    pyimgbox_close_mock = mocker.patch('pyimgbox.Gallery.close', AsyncMock())
    imghost = imgbox.ImgboxImageHost(cache_directory=tmp_path)
    with pytest.raises(errors.RequestError, match=r'^Something went wrong$'):
        await imghost._upload_image('foo.png')
    assert pyimgbox_close_mock.call_args_list == [call()]

@pytest.mark.asyncio
async def test_upload_image_closes_gallery_on_exception(tmp_path, mocker):
    mocker.patch('pyimgbox.Gallery.upload', AsyncMock(side_effect=RuntimeError('OH MY DOG')))
    pyimgbox_close_mock = mocker.patch('pyimgbox.Gallery.close', AsyncMock())
    imghost = imgbox.ImgboxImageHost(cache_directory=tmp_path)
    with pytest.raises(RuntimeError, match=r'^OH MY DOG$'):
        await imghost._upload_image('foo.png')
    assert pyimgbox_close_mock.call_args_list == [call()]
