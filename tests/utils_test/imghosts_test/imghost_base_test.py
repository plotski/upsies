import os
import re
from unittest.mock import Mock, PropertyMock, call

import pytest

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

        def __init__(self, *args, mock_cache=False, **kwargs):
            super().__init__(*args, **kwargs)
            self._upload_mock = AsyncMock()
            self._mock_cache = mock_cache
            self._get_info_from_cache_mock = Mock()
            self._store_info_to_cache_mock = Mock()

        async def _upload(self, image_path):
            return await self._upload_mock(image_path)

        def _get_info_from_cache(self, image_path):
            if self._mock_cache:
                return self._get_info_from_cache_mock(image_path)
            else:
                return super()._get_info_from_cache(image_path)

        def _store_info_to_cache(self, image_path, info):
            if self._mock_cache:
                return self._store_info_to_cache_mock(image_path, info)
            else:
                return super()._store_info_to_cache(image_path, info)

    return TestImageHost(**kwargs)


def test_cache_directory_property(mocker, tmp_path):
    mocker.patch('upsies.constants.CACHE_DIRPATH', 'mock/cache/path')
    imghost = make_TestImageHost()
    assert imghost.cache_directory == 'mock/cache/path'
    imghost = make_TestImageHost(cache_directory=tmp_path)
    assert imghost.cache_directory is tmp_path
    imghost.cache_directory = 'path/to/foo'
    assert imghost.cache_directory == 'path/to/foo'


def test_options_property():
    imghost = make_TestImageHost()
    assert imghost.options == {}
    imghost = make_TestImageHost(default_config={'foo': 1, 'bar': 2})
    assert imghost.options == {'foo': 1, 'bar': 2}
    imghost = make_TestImageHost(default_config={'foo': 1, 'bar': 2}, options={'bar': 99})
    assert imghost.options == {'foo': 1, 'bar': 99}


@pytest.mark.asyncio
async def test_upload_gets_info_from_upload_request(tmp_path):
    ih = make_TestImageHost(cache_directory=tmp_path, mock_cache=True)
    ih._get_info_from_cache_mock.return_value = None
    ih._upload_mock.return_value = {
        'url': 'http://foo.bar',
        'thumbnail_url': 'http://foo.bar/thumbnail',
        'delete_url': 'http://foo.bar/delete',
        'edit_url': 'http://foo.bar/edit',
    }
    image = await ih.upload('path/to/foo.png')
    assert ih._get_info_from_cache_mock.call_args_list == [call('path/to/foo.png')]
    assert ih._upload_mock.call_args_list == [call('path/to/foo.png')]
    assert ih._store_info_to_cache_mock.call_args_list == [call(
        'path/to/foo.png',
        {
            'url': 'http://foo.bar',
            'thumbnail_url': 'http://foo.bar/thumbnail',
            'delete_url': 'http://foo.bar/delete',
            'edit_url': 'http://foo.bar/edit',
        },
    )]
    assert isinstance(image, imghosts.UploadedImage)
    assert image == 'http://foo.bar'
    assert image.thumbnail_url == 'http://foo.bar/thumbnail'
    assert image.delete_url == 'http://foo.bar/delete'
    assert image.edit_url == 'http://foo.bar/edit'

@pytest.mark.asyncio
async def test_upload_gets_info_from_cache(tmp_path):
    ih = make_TestImageHost(cache_directory=tmp_path, mock_cache=True)
    ih._get_info_from_cache_mock.return_value = {
        'url': 'http://foo.bar',
        'thumbnail_url': 'http://foo.bar.cached/thumbnail',
        'delete_url': 'http://foo.bar.cached/delete',
        'edit_url': 'http://foo.bar.cached/edit',
    }
    image = await ih.upload('path/to/foo.png')
    assert ih._get_info_from_cache_mock.call_args_list == [call('path/to/foo.png')]
    assert ih._upload_mock.call_args_list == []
    assert ih._store_info_to_cache_mock.call_args_list == []
    assert isinstance(image, imghosts.UploadedImage)
    assert image == 'http://foo.bar'
    assert image.thumbnail_url == 'http://foo.bar.cached/thumbnail'
    assert image.delete_url == 'http://foo.bar.cached/delete'
    assert image.edit_url == 'http://foo.bar.cached/edit'

@pytest.mark.asyncio
async def test_upload_is_missing_url(tmp_path):
    ih = make_TestImageHost(cache_directory=tmp_path, mock_cache=True)
    ih._get_info_from_cache_mock.return_value = None
    ih._upload_mock.return_value = {}
    info_str = repr(ih._upload_mock.return_value)
    with pytest.raises(Exception, match=rf'^Missing "url" key in {re.escape(info_str)}$'):
        await ih.upload('path/to/foo.png')

@pytest.mark.asyncio
async def test_upload_with_cache_set_to_False(tmp_path):
    ih = make_TestImageHost(cache_directory=tmp_path, mock_cache=True)
    ih._get_info_from_cache_mock.return_value = {
        'url': 'http://foo.bar',
        'thumbnail_url': 'http://foo.bar.cached/thumbnail',
        'delete_url': 'http://foo.bar.cached/delete',
        'edit_url': 'http://foo.bar.cached/edit',
    }
    ih._upload_mock.return_value = {
        'url': 'http://foo.bar',
        'thumbnail_url': 'http://foo.bar/thumbnail',
        'delete_url': 'http://foo.bar/delete',
        'edit_url': 'http://foo.bar/edit',
    }
    image = await ih.upload('path/to/foo.png', cache=False)
    assert ih._get_info_from_cache_mock.call_args_list == []
    assert ih._upload_mock.call_args_list == [call('path/to/foo.png')]
    assert ih._store_info_to_cache_mock.call_args_list == [call(
        'path/to/foo.png',
        {
            'url': 'http://foo.bar',
            'thumbnail_url': 'http://foo.bar/thumbnail',
            'delete_url': 'http://foo.bar/delete',
            'edit_url': 'http://foo.bar/edit',
        },
    )]
    assert isinstance(image, imghosts.UploadedImage)
    assert image == 'http://foo.bar'
    assert image.thumbnail_url == 'http://foo.bar/thumbnail'
    assert image.delete_url == 'http://foo.bar/delete'
    assert image.edit_url == 'http://foo.bar/edit'


def test_get_info_from_cache_succeeds(tmp_path):
    imghost = make_TestImageHost(cache_directory=tmp_path)
    cache_file = imghost._cache_file(os.path.join(tmp_path, 'foo.png'))
    with open(cache_file, 'w') as f:
        f.write('{\n'
                '    "this": "and that"\n'
                '}\n')
    info = imghost._get_info_from_cache(image_path=os.path.join(tmp_path, 'foo.png'))
    assert info == {'this': 'and that'}
    assert os.path.exists(cache_file)

def test_get_info_from_cache_with_nonexisting_cache_file(tmp_path):
    imghost = make_TestImageHost(cache_directory=tmp_path)
    info = imghost._get_info_from_cache(image_path=os.path.join(tmp_path, 'foo.png'))
    assert info is None

def test_get_info_from_cache_fails_to_read(tmp_path):
    imghost = make_TestImageHost(cache_directory=tmp_path)
    cache_file = imghost._cache_file(os.path.join(tmp_path, 'foo.png'))
    with open(cache_file, 'w') as f:
        f.write('{\n'
                '    "this": "and that"\n'
                '}\n')
    os.chmod(cache_file, 0o000)
    try:
        info = imghost._get_info_from_cache(image_path=os.path.join(tmp_path, 'foo.png'))
    finally:
        os.chmod(cache_file, 0o600)
    assert info is None

def test_get_info_from_cache_fails_to_decode_json(tmp_path):
    imghost = make_TestImageHost(cache_directory=tmp_path)
    cache_file = imghost._cache_file(os.path.join(tmp_path, 'foo.png'))
    with open(cache_file, 'w') as f:
        f.write('{\n'
                '    "this": and that\n'
                '}\n')
    info = imghost._get_info_from_cache(image_path=os.path.join(tmp_path, 'foo.png'))
    assert info is None


def test_store_info_to_cache_succeeds(mocker, tmp_path):
    mkdir_mock = mocker.patch('upsies.utils.fs.mkdir')
    imghost = make_TestImageHost(cache_directory=tmp_path)
    imghost._store_info_to_cache(
        image_path=os.path.join(tmp_path, 'foo.png'),
        info={'this': 'and that'},
    )
    assert mkdir_mock.call_args_list == [call(str(tmp_path))]
    cache_file = imghost._cache_file(os.path.join(tmp_path, 'foo.png'))
    cache_content = open(cache_file, 'r').read()
    assert cache_content == ('{\n'
                             '    "this": "and that"\n'
                             '}\n')

def test_store_info_to_cache_fails_to_write(mocker, tmp_path):
    mkdir_mock = mocker.patch('upsies.utils.fs.mkdir')
    imghost = make_TestImageHost(cache_directory=tmp_path)
    cache_file = imghost._cache_file(os.path.join(tmp_path, 'foo.png'))
    os.chmod(tmp_path, 0o000)
    try:
        with pytest.raises(RuntimeError, match=rf'^Unable to write cache {cache_file}: Permission denied$'):
            imghost._store_info_to_cache(
                image_path=os.path.join(tmp_path, 'foo.png'),
                info={'this': 'and that'},
            )
        assert not os.path.exists(cache_file)
        assert mkdir_mock.call_args_list == [call(str(tmp_path))]
    finally:
        os.chmod(tmp_path, 0o700)

def test_store_info_to_cache_fails_to_encode_json(tmp_path):
    imghost = make_TestImageHost(cache_directory=tmp_path)
    cache_file = imghost._cache_file(os.path.join(tmp_path, 'foo.png'))
    with pytest.raises(RuntimeError, match=(rf'^Unable to write cache {cache_file}: '
                                            r"Object of type '?function'? is not JSON serializable$")):
        imghost._store_info_to_cache(
            image_path=os.path.join(tmp_path, 'foo.png'),
            info={'this': lambda: None},
        )
    assert not os.path.exists(cache_file)


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
    imghost = make_TestImageHost(cache_directory=cache_dir)
    mocker.patch.object(imghost, '_get_cache_id_as_string', return_value=cache_id)
    image_name = 'foo.png'

    if cache_id:
        exp_cache_name = f'{image_name}.{cache_id}.{imghost.name}.json'
    else:
        exp_cache_name = f'{image_name}.{imghost.name}.json'

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
    assert imghost._cache_file(image_path) == exp_cache_file


@pytest.mark.parametrize(
    argnames=('subclass_cache_id, options, exp_cache_id'),
    argvalues=(
        (None, {}, ''),
        (None, ['foo', 'bar', (1, 2, 3)], 'foo,bar,1,2,3'),
        (None, {'foo': 'bar', 'this': [23, 42], (1, 2, 3): 'baz'}, 'foo=bar,this=23,42,1,2,3=baz'),
        ('asdf', {'foo': 'bar'}, 'asdf'),
    ),
)
def test_cache_id(subclass_cache_id, options, exp_cache_id, mocker):
    imghost = make_TestImageHost()
    mocker.patch.object(type(imghost), 'options', PropertyMock(return_value=options))
    mocker.patch.object(type(imghost), 'cache_id', PropertyMock(return_value=subclass_cache_id))
    cache_id = imghost._get_cache_id_as_string()
    assert cache_id == exp_cache_id
