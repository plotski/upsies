from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.utils.imghosts import imgbox


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@patch('pyimgbox.Gallery')
def test_thumb_width_argument_not_given(Gallery_mock, tmp_path):
    imgbox.ImgboxImageHost(cache_directory=tmp_path)
    assert Gallery_mock.call_args_list == [call(
        thumb_width=imgbox.ImgboxImageHost.DEFAULT_THUMBNAIL_WIDTH,
        square_thumbs=False,
        comments_enabled=False,
    )]

@patch('pyimgbox.Gallery')
def test_thumb_width_argument_given(Gallery_mock, tmp_path):
    imgbox.ImgboxImageHost(thumb_width=200, cache_directory=tmp_path)
    assert Gallery_mock.call_args_list == [call(
        thumb_width=200,
        square_thumbs=False,
        comments_enabled=False,
    )]


@pytest.mark.asyncio
async def test_upload_handles_success(tmp_path, mocker):
    upload_mock = mocker.patch('pyimgbox.Gallery.upload', AsyncMock())
    imghost = imgbox.ImgboxImageHost(thumb_width=200, cache_directory=tmp_path)
    upload_mock.return_value = Mock(
        success=True,
        image_url='http://foo.url',
        thumbnail_url='http://foo.thumb.url',
        edit_url='http://foo.edit.url',
    )
    assert upload_mock.call_args_list == []
    info = await imghost._upload('foo.png')
    assert upload_mock.call_args_list == [call('foo.png')]
    assert info == {
        'url': 'http://foo.url',
        'thumb_url': 'http://foo.thumb.url',
        'edit_url': 'http://foo.edit.url',
    }

@pytest.mark.asyncio
async def test_upload_handles_error(tmp_path, mocker):
    upload_mock = mocker.patch('pyimgbox.Gallery.upload', AsyncMock())
    imghost = imgbox.ImgboxImageHost(thumb_width=200, cache_directory=tmp_path)
    upload_mock.return_value = Mock(
        success=False,
        error='Something went wrong',
    )
    with pytest.raises(errors.RequestError, match=r'^Something went wrong$'):
        await imghost._upload('foo.png')
