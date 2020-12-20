from upsies.utils.imghosts import common


def test_UploadedImage_is_URL_string():
    image = common.UploadedImage('http://url.to/image.jpg')
    assert image == 'http://url.to/image.jpg'

def test_UploadedImage_kwargs_are_attributes():
    image = common.UploadedImage(
        'http://url.to/image.jpg',
        more_info='foo',
        also_this='bar',
    )
    assert image.more_info == 'foo'
    assert image.also_this == 'bar'

def test_UploadedImage_repr():
    image = common.UploadedImage(
        'http://url.to/image.jpg',
        more_info='foo',
        also_this='bar',
    )
    assert repr(image) == ("UploadedImage('http://url.to/image.jpg', "
                           "more_info='foo', also_this='bar')")
