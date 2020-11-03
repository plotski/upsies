from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.tools.imghost import imgbox


@patch('pyimgbox.Gallery')
def test_thumb_width_argument_not_given(Gallery_mock, tmp_path):
    imgbox.Uploader(cache_dir=tmp_path)
    assert Gallery_mock.call_args_list == [call(
        thumb_width=imgbox.Uploader.DEFAULT_THUMBNAIL_WIDTH,
        square_thumbs=False,
        comments_enabled=False,
    )]

@patch('pyimgbox.Gallery')
def test_thumb_width_argument_given(Gallery_mock, tmp_path):
    imgbox.Uploader(thumb_width=200, cache_dir=tmp_path)
    assert Gallery_mock.call_args_list == [call(
        thumb_width=200,
        square_thumbs=False,
        comments_enabled=False,
    )]


@patch('pyimgbox.Gallery.upload')
@pytest.mark.asyncio
async def test_upload_handles_success(upload_mock, tmp_path):
    uploader = imgbox.Uploader(thumb_width=200, cache_dir=tmp_path)
    upload_mock.return_value = Mock(
        success=True,
        image_url='http://foo.url',
        thumbnail_url='http://foo.thumb.url',
        edit_url='http://foo.edit.url',
    )
    assert upload_mock.call_args_list == []
    info = await uploader._upload('foo.png')
    assert upload_mock.call_args_list == [call('foo.png')]
    assert info == {
        'url': 'http://foo.url',
        'thumb_url': 'http://foo.thumb.url',
        'edit_url': 'http://foo.edit.url',
    }

@patch('pyimgbox.Gallery.upload')
@pytest.mark.asyncio
async def test_upload_handles_error(upload_mock, tmp_path):
    uploader = imgbox.Uploader(thumb_width=200, cache_dir=tmp_path)
    upload_mock.return_value = Mock(
        success=False,
        error='Something went wrong',
    )
    with pytest.raises(errors.RequestError, match=r'^Something went wrong$'):
        await uploader._upload('foo.png')
