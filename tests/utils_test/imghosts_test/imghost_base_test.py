import os
import re
from unittest.mock import Mock, call, patch

import pytest

from upsies.utils import imghosts


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_imghosts(mocker):
    existing_imghosts = (Mock(), Mock(), Mock())
    submodules_mock = mocker.patch('upsies.utils.imghosts.submodules')
    subclasses_mock = mocker.patch('upsies.utils.imghosts.subclasses', return_value=existing_imghosts)
    assert imghosts.imghosts() == existing_imghosts
    assert submodules_mock.call_args_list == [call('upsies.utils.imghosts')]
    assert subclasses_mock.call_args_list == [call(imghosts.base.ImageHostBase, submodules_mock.return_value)]


def test_imghost_returns_ImageHostBase_instance(mocker):
    existing_imghosts = (Mock(), Mock(), Mock())
    existing_imghosts[0].configure_mock(name='foo')
    existing_imghosts[1].configure_mock(name='bar')
    existing_imghosts[2].configure_mock(name='baz')
    mocker.patch('upsies.utils.imghosts.imghosts', return_value=existing_imghosts)
    assert imghosts.imghost('bar', x=123) is existing_imghosts[1].return_value
    assert existing_imghosts[1].call_args_list == [call(x=123)]

def test_imghost_fails_to_find_imghost(mocker):
    existing_imghosts = (Mock(), Mock(), Mock())
    existing_imghosts[0].configure_mock(name='foo')
    existing_imghosts[1].configure_mock(name='bar')
    existing_imghosts[2].configure_mock(name='baz')
    mocker.patch('upsies.utils.imghosts.imghosts', return_value=existing_imghosts)
    with pytest.raises(ValueError, match='^Unsupported image hosting service: bam$'):
        imghosts.imghost('bam', x=123)
    for ih in existing_imghosts:
        assert ih.call_args_list == []


@pytest.mark.parametrize('method', imghosts.ImageHostBase.__abstractmethods__)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in imghosts.ImageHostBase.__abstractmethods__}
    del attrs[method]
    cls = type('TestImageHost', (imghosts.ImageHostBase,), attrs)
    # Python 3.9 changed "methods" to "method"
    exp_msg = rf"^Can't instantiate abstract class TestImageHost with abstract methods? {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def make_TestImageHost(**kwargs):
    class TestImageHost(imghosts.ImageHostBase):
        name = 'imgw00t'

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


@pytest.mark.parametrize(
    argnames=('cache_dir', 'exp_cache_dir'),
    argvalues=(
        (None, '/tmp/path'),
        ('some/path', 'some/path'),
    ),
)
@pytest.mark.parametrize('image_dir', (None, 'some/relative/path', '/absolute/path'))
@patch('upsies.utils.fs.tmpdir')
def test_cache_file_with_default_cache_dir(tmpdir_mock, image_dir, cache_dir, exp_cache_dir):
    tmpdir_mock.return_value = exp_cache_dir
    imghost = make_TestImageHost(cache_dir=cache_dir)
    image_name = 'foo.png'
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


def test_store_info_to_cache_succeeds(tmp_path):
    imghost = make_TestImageHost(cache_dir=tmp_path)
    imghost._store_info_to_cache(
        image_path=os.path.join(tmp_path, 'foo.png'),
        info={'this': 'and that'},
    )
    cache_file = imghost._cache_file(os.path.join(tmp_path, 'foo.png'))
    cache_content = open(cache_file, 'r').read()
    assert cache_content == ('{\n'
                             '    "this": "and that"\n'
                             '}\n')

def test_store_info_to_cache_fails_to_write(tmp_path):
    imghost = make_TestImageHost(cache_dir=tmp_path)
    cache_file = imghost._cache_file(os.path.join(tmp_path, 'foo.png'))
    os.chmod(tmp_path, 0o000)
    try:
        with pytest.raises(RuntimeError, match=rf'^Unable to write cache {cache_file}: Permission denied$'):
            imghost._store_info_to_cache(
                image_path=os.path.join(tmp_path, 'foo.png'),
                info={'this': 'and that'},
            )
    finally:
        os.chmod(tmp_path, 0o700)
        assert not os.path.exists(cache_file)

def test_store_info_to_cache_fails_to_encode_json(tmp_path):
    imghost = make_TestImageHost(cache_dir=tmp_path)
    cache_file = imghost._cache_file(os.path.join(tmp_path, 'foo.png'))
    with pytest.raises(RuntimeError, match=(rf'^Unable to write cache {cache_file}: '
                                            r"Object of type '?function'? is not JSON serializable$")):
        imghost._store_info_to_cache(
            image_path=os.path.join(tmp_path, 'foo.png'),
            info={'this': lambda: None},
        )
    assert not os.path.exists(cache_file)


def test_get_info_from_cache_succeeds(tmp_path):
    imghost = make_TestImageHost(cache_dir=tmp_path)
    cache_file = imghost._cache_file(os.path.join(tmp_path, 'foo.png'))
    with open(cache_file, 'w') as f:
        f.write('{\n'
                '    "this": "and that"\n'
                '}\n')
    info = imghost._get_info_from_cache(image_path=os.path.join(tmp_path, 'foo.png'))
    assert info == {'this': 'and that'}
    assert os.path.exists(cache_file)

def test_get_info_from_cache_fails_to_read(tmp_path):
    imghost = make_TestImageHost(cache_dir=tmp_path)
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
    imghost = make_TestImageHost(cache_dir=tmp_path)
    cache_file = imghost._cache_file(os.path.join(tmp_path, 'foo.png'))
    with open(cache_file, 'w') as f:
        f.write('{\n'
                '    "this": and that\n'
                '}\n')
    info = imghost._get_info_from_cache(image_path=os.path.join(tmp_path, 'foo.png'))
    assert info is None


@pytest.mark.asyncio
async def test_upload_gets_info_from_upload():
    ih = make_TestImageHost(mock_cache=True)
    ih._get_info_from_cache_mock.return_value = None
    ih._upload_mock.return_value = {
        'url': 'http://foo.bar',
        'more': 'info',
    }
    image = await ih.upload('path/to/foo.png')
    assert ih._get_info_from_cache_mock.call_args_list == [call('path/to/foo.png')]
    assert ih._upload_mock.call_args_list == [call('path/to/foo.png')]
    assert ih._store_info_to_cache_mock.call_args_list == [call(
        'path/to/foo.png',
        {'url': 'http://foo.bar', 'more': 'info'},
    )]
    assert isinstance(image, imghosts.UploadedImage)
    assert image == 'http://foo.bar'
    assert image.more == 'info'

@pytest.mark.asyncio
async def test_upload_gets_info_from_cache():
    ih = make_TestImageHost(mock_cache=True)
    ih._get_info_from_cache_mock.return_value = {
        'url': 'http://foo.bar',
        'more': 'info',
    }
    image = await ih.upload('path/to/foo.png')
    assert ih._get_info_from_cache_mock.call_args_list == [call('path/to/foo.png')]
    assert ih._upload_mock.call_args_list == []
    assert ih._store_info_to_cache_mock.call_args_list == []
    assert isinstance(image, imghosts.UploadedImage)
    assert image == 'http://foo.bar'
    assert image.more == 'info'

@pytest.mark.asyncio
async def test_upload_ignores_cache():
    ih = make_TestImageHost(mock_cache=True)
    ih._get_info_from_cache_mock.return_value = {
        'url': 'http://foo.bar',
        'more': 'info',
    }
    ih._upload_mock.return_value = {
        'url': 'http://baz.png',
        'more': 'other info',
    }
    image = await ih.upload('path/to/foo.png', force=True)
    assert ih._get_info_from_cache_mock.call_args_list == []
    assert ih._upload_mock.call_args_list == [call('path/to/foo.png')]
    assert ih._store_info_to_cache_mock.call_args_list == [call(
        'path/to/foo.png',
        {'url': 'http://baz.png', 'more': 'other info'},
    )]
    assert isinstance(image, imghosts.UploadedImage)
    assert image == 'http://baz.png'
    assert image.more == 'other info'

@pytest.mark.asyncio
async def test_upload_is_missing_url():
    ih = make_TestImageHost(mock_cache=True)
    ih._get_info_from_cache_mock.return_value = None
    ih._upload_mock.return_value = {
        'foo': 'http://foo.bar',
        'more': 'info',
    }
    info_str = repr(ih._upload_mock.return_value)
    with pytest.raises(Exception, match=rf'^Missing "url" key in {re.escape(info_str)}$'):
        await ih.upload('path/to/foo.png')
