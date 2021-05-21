from upsies.utils.imghosts import common

import pytest


def test_UploadedImage_is_URL_string():
    image = common.UploadedImage('http://url.to/image.jpg')
    assert image == 'http://url.to/image.jpg'
    assert isinstance(image, str)
    assert repr(image) == "UploadedImage('http://url.to/image.jpg')"


def test_UploadedImage_thumbnail_url():
    image = common.UploadedImage(
        'http://url.to/image.jpg',
        thumbnail_url='http://url.to/image.thumbnail.jpg',
    )
    assert image.thumbnail_url == 'http://url.to/image.thumbnail.jpg'
    with pytest.raises(AttributeError, match=r"^can't set attribute$"):
        image.thumbnail_url = 'foo'
    assert repr(image) == "UploadedImage('http://url.to/image.jpg', thumbnail_url='http://url.to/image.thumbnail.jpg')"


def test_UploadedImage_delete_url():
    image = common.UploadedImage(
        'http://url.to/image.jpg',
        delete_url='http://url.to/image.jpg/delete',
    )
    assert image.delete_url == 'http://url.to/image.jpg/delete'
    with pytest.raises(AttributeError, match=r"^can't set attribute$"):
        image.delete_url = 'foo'
    assert str(image) == 'http://url.to/image.jpg'
    assert repr(image) == "UploadedImage('http://url.to/image.jpg', delete_url='http://url.to/image.jpg/delete')"


def test_UploadedImage_edit_url():
    image = common.UploadedImage(
        'http://url.to/image.jpg',
        edit_url='http://url.to/image.jpg/edit',
    )
    assert image.edit_url == 'http://url.to/image.jpg/edit'
    with pytest.raises(AttributeError, match=r"^can't set attribute$"):
        image.edit_url = 'foo'
    assert str(image) == 'http://url.to/image.jpg'
    assert repr(image) == "UploadedImage('http://url.to/image.jpg', edit_url='http://url.to/image.jpg/edit')"


@pytest.mark.parametrize(
    argnames='kwargs, exp_repr',
    argvalues=(
        ({'thumbnail_url': 'http://url.to/image.thumbnail.jpg'},
         "UploadedImage('http://url.to/image.jpg', thumbnail_url='http://url.to/image.thumbnail.jpg')"),
        ({'delete_url': 'http://url.to/image.delete.jpg'},
         "UploadedImage('http://url.to/image.jpg', delete_url='http://url.to/image.delete.jpg')"),
        ({'thumbnail_url': 'http://url.to/image.thumbnail.jpg',
         'delete_url': 'http://url.to/image.delete.jpg'},
         ("UploadedImage('http://url.to/image.jpg', "
          "thumbnail_url='http://url.to/image.thumbnail.jpg', "
          "delete_url='http://url.to/image.delete.jpg')")),
    ),
)
def test_UploadedImage_repr(kwargs, exp_repr):
    image = common.UploadedImage('http://url.to/image.jpg', **kwargs)
    assert repr(image) == exp_repr
