from types import SimpleNamespace
from unittest.mock import PropertyMock, call, patch

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


@patch('pyimgbox.Gallery')
def test_upload_creates_gallery_on_first_upload(Gallery_mock, tmp_path):
    uploader = imgbox.Uploader(thumb_width=200, cache_dir=tmp_path)
    type(Gallery_mock.return_value).created = PropertyMock(return_value=False)
    Gallery_mock.return_value.add.return_value = (
        SimpleNamespace(
            success=True,
            image_url='http://foo.url',
            thumbnail_url='http://foo.thumb.url',
            edit_url='http://foo.edit.url',
        ),
    )
    assert Gallery_mock.return_value.create.call_args_list == []
    uploader._upload('foo.png')
    assert Gallery_mock.return_value.create.call_args_list == [call()]
    type(Gallery_mock.return_value).created = PropertyMock(return_value=True)
    uploader._upload('bar.png')
    assert Gallery_mock.return_value.create.call_args_list == [call()]
    uploader._upload('baz.png')
    assert Gallery_mock.return_value.create.call_args_list == [call()]

@patch('pyimgbox.Gallery')
def test_upload_returns_urls(Gallery_mock, tmp_path):
    uploader = imgbox.Uploader(thumb_width=200, cache_dir=tmp_path)
    Gallery_mock.return_value.add.return_value = (
        SimpleNamespace(
            success=True,
            image_url='http://foo.url',
            thumbnail_url='http://foo.thumb.url',
            edit_url='http://foo.edit.url',
        ),
    )
    info = uploader._upload('foo.png')
    assert info == {
        'url': 'http://foo.url',
        'thumb_url': 'http://foo.thumb.url',
        'edit_url': 'http://foo.edit.url',
    }

@patch('pyimgbox.Gallery')
def test_upload_raises_RequestError(Gallery_mock, tmp_path):
    uploader = imgbox.Uploader(thumb_width=200, cache_dir=tmp_path)
    Gallery_mock.return_value.add.return_value = (
        SimpleNamespace(
            success=False,
            error='Something went wrong',
        ),
    )
    with pytest.raises(errors.RequestError, match=r'^Something went wrong$'):
        uploader._upload('foo.png')
