import copy
import os
import re
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies import errors
from upsies.utils import imghosts


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def make_TestImageHost(default_config=None, **kwargs):
    # Avoid NameError bug
    default_config_ = default_config

    class TestImageHost(imghosts.ImageHostBase):
        name = 'imgw00t'
        default_config = default_config_ or {}

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._upload_image_mock = AsyncMock()

        async def _upload_image(self, image_path):
            return await self._upload_image_mock(image_path)

    return TestImageHost(**kwargs)


def test_cache_directory_property(mocker, tmp_path):
    mocker.patch('upsies.constants.CACHE_DIRPATH', 'mock/cache/path')
    imghost = make_TestImageHost()
    assert imghost.cache_directory == 'mock/cache/path'
    imghost = make_TestImageHost(cache_directory=tmp_path)
    assert imghost.cache_directory is tmp_path
    imghost.cache_directory = 'path/to/foo'
    assert imghost.cache_directory == 'path/to/foo'


def test_default_config_without_custom_defaults():
    imghost = make_TestImageHost()
    default_config_common = copy.deepcopy(imghost.default_config_common)
    exp_default_config = {**default_config_common, **imghost.default_config}
    assert imghost.default_config == exp_default_config
    exp_options = {**imghost.default_config}
    assert imghost.options == exp_options
    assert imghost.default_config_common == default_config_common

def test_default_config_with_custom_defaults():
    imghost = make_TestImageHost(default_config={'foo': 1, 'bar': 2})
    default_config_common = copy.deepcopy(imghost.default_config_common)
    exp_default_config = {**default_config_common, **{'foo': 1, 'bar': 2}}
    assert imghost.default_config == exp_default_config
    exp_options = exp_default_config
    assert imghost.options == exp_options
    assert imghost.default_config_common == default_config_common

def test_default_config_with_custom_defaults_and_custom_options():
    imghost = make_TestImageHost(default_config={'foo': 1, 'bar': 2}, options={'foo': 1, 'bar': 99})
    default_config_common = copy.deepcopy(imghost.default_config_common)
    exp_default_config = {**default_config_common, **{'foo': 1, 'bar': 2}}
    assert imghost.default_config == exp_default_config
    exp_options = {**imghost.default_config, **{'foo': 1, 'bar': 99}}
    assert imghost.options == exp_options
    assert imghost.default_config_common == default_config_common

def test_default_config_with_overloaded_common_defaults():
    default_config_key = tuple(imghosts.ImageHostBase.default_config_common)[0]
    default_config = {default_config_key: 'foozbar'}
    imghost = make_TestImageHost(default_config=default_config)
    default_config_common = copy.deepcopy(imghost.default_config_common)
    exp_default_config = {**default_config_common, **{default_config_key: 'foozbar'}}
    assert imghost.default_config == exp_default_config
    exp_options = exp_default_config
    assert imghost.options == exp_options
    assert imghost.default_config_common == default_config_common


def test_options_property():
    imghost = make_TestImageHost()
    assert imghost.options == {'thumb_width': 0}
    imghost = make_TestImageHost(default_config={'foo': 1, 'bar': 2})
    assert imghost.options == {'thumb_width': 0, 'foo': 1, 'bar': 2}
    imghost = make_TestImageHost(default_config={'foo': 1, 'bar': 2}, options={'bar': 99})
    assert imghost.options == {'thumb_width': 0, 'foo': 1, 'bar': 99}


@pytest.mark.parametrize('cache', (True, False))
@pytest.mark.parametrize('thumb_width', (0, 123))
@pytest.mark.asyncio
async def test_upload_succeeds(thumb_width, cache, mocker, tmp_path):
    resize_mock = mocker.patch('upsies.utils.image.resize', return_value='thumbnail.png')

    ih = make_TestImageHost(cache_directory=tmp_path, options={'thumb_width': thumb_width})
    image_urls = ['https://localhost:123/foo.png']
    if thumb_width:
        image_urls.append('https://localhost:123/foo.thumb.png')
    mocker.patch.object(ih, '_get_image_url', AsyncMock(side_effect=image_urls))

    image = await ih.upload('path/to/foo.png', cache=cache)

    if thumb_width:
        assert resize_mock.call_args_list == [call(
            'path/to/foo.png',
            width=thumb_width,
            target_directory=ih.cache_directory,
        )]
        assert ih._get_image_url.call_args_list == [
            call('path/to/foo.png', cache=cache),
            call(resize_mock.return_value, cache=cache),
        ]
    else:
        assert ih._get_image_url.call_args_list == [
            call('path/to/foo.png', cache=cache),
        ]

    assert isinstance(image, imghosts.UploadedImage)
    assert image == image_urls[0]
    if thumb_width:
        assert image.thumbnail_url == image_urls[1]
    else:
        assert image.thumbnail_url is None

@pytest.mark.parametrize(
    argnames='cache, resize_error, exp_request_error',
    argvalues=(
        (False, errors.ImageResizeError('not an image'), errors.RequestError('not an image')),
        (True, errors.ImageResizeError('not an image'), errors.RequestError('not an image')),
    ),
)
@pytest.mark.asyncio
async def test_upload_catches_ResizeError(cache, resize_error, exp_request_error, mocker, tmp_path):
    resize_mock = mocker.patch('upsies.utils.image.resize', side_effect=resize_error)

    ih = make_TestImageHost(cache_directory=tmp_path, options={'thumb_width': 345})
    image_urls = ['https://localhost:123/foo.png', 'https://localhost:123/foo.thumb.png']
    mocker.patch.object(ih, '_get_image_url', AsyncMock(side_effect=image_urls))

    with pytest.raises(type(exp_request_error), match=rf'^path/to/foo.png: {re.escape(str(exp_request_error))}$'):
        await ih.upload('path/to/foo.png', cache=cache)

    assert resize_mock.call_args_list == [call(
        'path/to/foo.png',
        width=345,
        target_directory=ih.cache_directory,
    )]
    assert ih._get_image_url.call_args_list == [
        call('path/to/foo.png', cache=cache),
    ]


@pytest.mark.asyncio
async def test_get_image_url_from_cache(mocker, tmp_path):
    ih = make_TestImageHost(cache_directory=tmp_path)
    mocker.patch.object(ih, '_upload_image', AsyncMock(return_value='http://localhost:123/uploaded.image.jpg'))
    mocker.patch.object(ih, '_get_url_from_cache', Mock(return_value='http://localhost:123/cached.image.jpg'))
    mocker.patch.object(ih, '_store_url_to_cache')
    url = await ih._get_image_url('path/to/image.jpg', cache=True)
    assert url == 'http://localhost:123/cached.image.jpg'
    assert ih._get_url_from_cache.call_args_list == [call('path/to/image.jpg')]
    assert ih._upload_image.call_args_list == []
    assert ih._store_url_to_cache.call_args_list == []

@pytest.mark.asyncio
async def test_get_image_url_from_upload(mocker, tmp_path):
    ih = make_TestImageHost(cache_directory=tmp_path)
    mocker.patch.object(ih, '_upload_image', AsyncMock(return_value='http://localhost:123/uploaded.image.jpg'))
    mocker.patch.object(ih, '_get_url_from_cache', Mock(return_value='http://localhost:123/cached.image.jpg'))
    mocker.patch.object(ih, '_store_url_to_cache')
    url = await ih._get_image_url('path/to/image.jpg', cache=False)
    assert url == 'http://localhost:123/uploaded.image.jpg'
    assert ih._get_url_from_cache.call_args_list == []
    assert ih._upload_image.call_args_list == [call('path/to/image.jpg')]
    assert ih._store_url_to_cache.call_args_list == [call(
        'path/to/image.jpg',
        'http://localhost:123/uploaded.image.jpg',
    )]

@pytest.mark.asyncio
async def test_get_image_url_prepends_image_path_to_request_error(mocker, tmp_path):
    ih = make_TestImageHost(cache_directory=tmp_path)
    mocker.patch.object(ih, '_upload_image', AsyncMock(side_effect=errors.RequestError('Connection refused')))
    mocker.patch.object(ih, '_get_url_from_cache', Mock(return_value='http://localhost:123/cached.image.jpg'))
    mocker.patch.object(ih, '_store_url_to_cache')
    with pytest.raises(errors.RequestError, match=r'^path/to/image.jpg: Connection refused$'):
        await ih._get_image_url('path/to/image.jpg', cache=False)
    assert ih._get_url_from_cache.call_args_list == []
    assert ih._upload_image.call_args_list == [call('path/to/image.jpg')]
    assert ih._store_url_to_cache.call_args_list == []


def test_get_url_from_cache_succeeds(tmp_path):
    ih = make_TestImageHost(cache_directory=tmp_path)
    image_filepath = os.path.join(tmp_path, 'foo.png')
    cache_file = ih._cache_file(image_filepath)
    with open(cache_file, 'w') as f:
        f.write('http://localhost:123/foo.png')
    url = ih._get_url_from_cache(image_path=image_filepath)
    assert url == 'http://localhost:123/foo.png'

def test_get_url_from_cache_with_nonexisting_cache_file(tmp_path):
    ih = make_TestImageHost(cache_directory=tmp_path)
    image_filepath = os.path.join(tmp_path, 'foo.png')
    url = ih._get_url_from_cache(image_path=image_filepath)
    assert url is None

def test_get_url_from_cache_fails_to_read_cache_file(tmp_path):
    ih = make_TestImageHost(cache_directory=tmp_path)
    cache_file = ih._cache_file(os.path.join(tmp_path, 'foo.png'))
    with open(cache_file, 'w') as f:
        f.write('secret')
    os.chmod(cache_file, 0o000)
    try:
        url = ih._get_url_from_cache(image_path=os.path.join(tmp_path, 'foo.png'))
    finally:
        os.chmod(cache_file, 0o600)
    assert url is None


def test_store_url_to_cache_succeeds(mocker, tmp_path):
    mkdir_mock = mocker.patch('upsies.utils.fs.mkdir')
    ih = make_TestImageHost(cache_directory=tmp_path)
    ih._store_url_to_cache(
        image_path=os.path.join(tmp_path, 'foo.png'),
        url='http://localhost:123/image.jpg',
    )
    assert mkdir_mock.call_args_list == [call(str(tmp_path))]
    cache_file = ih._cache_file(os.path.join(tmp_path, 'foo.png'))
    cache_content = open(cache_file, 'r').read()
    assert cache_content == 'http://localhost:123/image.jpg'

def test_store_url_to_cache_fails_to_write(mocker, tmp_path):
    mkdir_mock = mocker.patch('upsies.utils.fs.mkdir')
    ih = make_TestImageHost(cache_directory=tmp_path)
    cache_file = ih._cache_file(os.path.join(tmp_path, 'foo.png'))
    os.chmod(tmp_path, 0o000)
    try:
        with pytest.raises(RuntimeError, match=rf'^Unable to write cache {cache_file}: Permission denied$'):
            ih._store_url_to_cache(
                image_path=os.path.join(tmp_path, 'foo.png'),
                url='http://localhost:123/image.jpg',
            )
        assert not os.path.exists(cache_file)
        assert mkdir_mock.call_args_list == [call(str(tmp_path))]
    finally:
        os.chmod(tmp_path, 0o700)


@pytest.mark.parametrize(
    argnames=('cache_dir', 'cache_id', 'exp_cache_dir'),
    argvalues=(
        (None, None, '/tmp/path'),
        (None, 0, '/tmp/path'),
        (None, '', '/tmp/path'),
        (None, 'image_id', '/tmp/path'),
        ('some/path', None, 'some/path'),
        ('some/path', 0, 'some/path'),
        ('some/path', '', 'some/path'),
        ('some/path', 'image_id', 'some/path'),
    ),
)
@pytest.mark.parametrize('image_dir', (None, 'some/relative/path', '/absolute/path'))
def test_cache_file(mocker, image_dir, cache_dir, cache_id, exp_cache_dir):
    mocker.patch('upsies.constants.CACHE_DIRPATH', exp_cache_dir)
    ih = make_TestImageHost(cache_directory=cache_dir)
    mocker.patch.object(ih, '_get_cache_id_as_string', return_value=cache_id)
    image_name = 'foo.png'

    if cache_id:
        exp_cache_name = f'{image_name}.{cache_id}.{ih.name}.url'
    else:
        exp_cache_name = f'{image_name}.{ih.name}.url'

    if image_dir is None:
        # Image is in cache dir
        image_path = os.path.join(exp_cache_dir, image_name)
    elif os.path.isabs(image_dir):
        # Image has absolute path
        image_path = os.path.join(image_dir, image_name)
        exp_cache_name = os.path.join(os.path.dirname(image_path), exp_cache_name).replace(os.sep, '_')
    else:
        # Image has relative path
        image_path = os.path.join(os.getcwd(), image_dir, image_name)
        exp_cache_name = os.path.join(os.path.dirname(image_path), exp_cache_name).replace(os.sep, '_')

    exp_cache_file = os.path.join(exp_cache_dir, exp_cache_name)
    assert ih._cache_file(image_path) == exp_cache_file


@pytest.mark.parametrize(
    argnames=('cache_id, exp_cache_id'),
    argvalues=(
        (None, None),
        (23, '23'),
        ('asdf', 'asdf'),
        (['foo', 'bar', (1, 2, 3)], 'foo,bar,1,2,3'),
        ({'foo': 'bar', 'this': [23, 42], (1, 2, 3): 'baz'}, 'foo=bar,this=23,42,1,2,3=baz'),
    ),
)
def test_get_cache_id_as_string(cache_id, exp_cache_id, mocker):
    ih = make_TestImageHost()
    mocker.patch.object(type(ih), 'cache_id', PropertyMock(return_value=cache_id))
    cache_id = ih._get_cache_id_as_string()
    assert cache_id == exp_cache_id
