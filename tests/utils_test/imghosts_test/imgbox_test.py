from unittest.mock import Mock, call, patch

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


def test_default_config():
    assert imgbox.ImgboxImageHost.default_config == {
        'thumb_width': 0,
    }


@pytest.mark.asyncio
async def test_cache_id(tmp_path, mocker):
    mocker.patch('pyimgbox.Gallery', return_value=Mock(thumb_width=12342))
    imghost = imgbox.ImgboxImageHost(cache_directory=tmp_path)
    assert imghost.cache_id == {'thumb_width': 12342}


@patch('pyimgbox.Gallery')
def test_init(Gallery_mock, tmp_path):
    imghost = imgbox.ImgboxImageHost(cache_directory=tmp_path)
    assert imghost._gallery is Gallery_mock.return_value
    assert Gallery_mock.call_args_list == [call(
        thumb_width=imghost.options['thumb_width'],
        square_thumbs=False,
        comments_enabled=False,
    )]


@pytest.mark.asyncio
async def test_upload_handles_success(tmp_path, mocker):
    upload_mock = mocker.patch('pyimgbox.Gallery.upload', AsyncMock())
    imghost = imgbox.ImgboxImageHost(cache_directory=tmp_path)
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
        'thumbnail_url': 'http://foo.thumb.url',
        'edit_url': 'http://foo.edit.url',
    }

@pytest.mark.asyncio
async def test_upload_handles_error(tmp_path, mocker):
    upload_mock = mocker.patch('pyimgbox.Gallery.upload', AsyncMock())
    imghost = imgbox.ImgboxImageHost(cache_directory=tmp_path)
    upload_mock.return_value = Mock(
        success=False,
        error='Something went wrong',
    )
    with pytest.raises(errors.RequestError, match=r'^Something went wrong$'):
        await imghost._upload('foo.png')
