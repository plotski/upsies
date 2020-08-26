import os
import re
from unittest.mock import Mock, call, patch

import pytest

from upsies.tools.imghost._base import UploaderBase
from upsies.tools.imghost._common import UploadedImage

abstract_methods = (
    'name', '_upload'
)

@pytest.mark.parametrize('method', abstract_methods)
def test_abstract_methods(method):
    attrs = {name:lambda self: None for name in abstract_methods}
    del attrs[method]
    cls = type('TestUploader', (UploaderBase,), attrs)
    exp_msg = rf"^Can't instantiate abstract class TestUploader with abstract methods {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def make_TestUploader(**kwargs):
    class TestUploader(UploaderBase):
        name = 'imgw00t'

        def __init__(self, *args, mock_cache=False, **kwargs):
            super().__init__(*args, **kwargs)
            self._upload_mock = Mock()
            self._mock_cache = mock_cache
            self._get_info_from_cache_mock = Mock()
            self._store_info_to_cache_mock = Mock()

        def _upload(self, image_path):
            return self._upload_mock(image_path)

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

    return TestUploader(**kwargs)


@patch('upsies.utils.fs.tmpdir')
def test_cache_file_without_given_cache_dir(tmpdir_mock):
    tmpdir_mock.return_value = '/tmp/path'
    uploader = make_TestUploader()
    assert uploader._cache_file('foo.png') == f'/tmp/path/foo.png.{uploader.name}.json'

def test_cache_file_with_given_cache_dir():
    uploader = make_TestUploader(cache_dir='some/path')
    assert uploader._cache_file('foo.png') == f'some/path/foo.png.{uploader.name}.json'


def test_store_info_to_cache_succeeds(tmp_path):
    uploader = make_TestUploader(cache_dir=tmp_path)
    uploader._store_info_to_cache(
        image_path=os.path.join(tmp_path, 'foo.png'),
        info={'this': 'and that'},
    )
    cache_file = uploader._cache_file(os.path.join(tmp_path, 'foo.png'))
    cache_content = open(cache_file, 'r').read()
    assert cache_content == ('{\n'
                             '    "this": "and that"\n'
                             '}\n')

def test_store_info_to_cache_fails_to_write(tmp_path):
    uploader = make_TestUploader(cache_dir=tmp_path)
    cache_file = uploader._cache_file(os.path.join(tmp_path, 'foo.png'))
    os.chmod(tmp_path, 0o000)
    try:
        with pytest.raises(RuntimeError, match=rf'^Unable to write cache {cache_file}: Permission denied$'):
            uploader._store_info_to_cache(
                image_path=os.path.join(tmp_path, 'foo.png'),
                info={'this': 'and that'},
            )
    finally:
        os.chmod(tmp_path, 0o700)
        assert not os.path.exists(cache_file)

def test_store_info_to_cache_fails_to_encode_json(tmp_path):
    uploader = make_TestUploader(cache_dir=tmp_path)
    cache_file = uploader._cache_file(os.path.join(tmp_path, 'foo.png'))
    with pytest.raises(RuntimeError, match=(rf'^Unable to write cache {cache_file}: '
                                            r'Object of type function is not JSON serializable$')):
        uploader._store_info_to_cache(
            image_path=os.path.join(tmp_path, 'foo.png'),
            info={'this': lambda: None},
        )
    assert not os.path.exists(cache_file)


def test_get_info_from_cache_succeeds(tmp_path):
    uploader = make_TestUploader(cache_dir=tmp_path)
    cache_file = uploader._cache_file(os.path.join(tmp_path, 'foo.png'))
    with open(cache_file, 'w') as f:
        f.write('{\n'
                '    "this": "and that"\n'
                '}\n')
    info = uploader._get_info_from_cache(image_path=os.path.join(tmp_path, 'foo.png'))
    assert info == {'this': 'and that'}
    assert os.path.exists(cache_file)

def test_get_info_from_cache_fails_to_read(tmp_path):
    uploader = make_TestUploader(cache_dir=tmp_path)
    cache_file = uploader._cache_file(os.path.join(tmp_path, 'foo.png'))
    with open(cache_file, 'w') as f:
        f.write('{\n'
                '    "this": "and that"\n'
                '}\n')
    os.chmod(cache_file, 0o000)
    try:
        info = uploader._get_info_from_cache(image_path=os.path.join(tmp_path, 'foo.png'))
    finally:
        os.chmod(cache_file, 0o600)
    assert info is None

def test_get_info_from_cache_fails_to_decode_json(tmp_path):
    uploader = make_TestUploader(cache_dir=tmp_path)
    cache_file = uploader._cache_file(os.path.join(tmp_path, 'foo.png'))
    with open(cache_file, 'w') as f:
        f.write('{\n'
                '    "this": and that\n'
                '}\n')
    info = uploader._get_info_from_cache(image_path=os.path.join(tmp_path, 'foo.png'))
    assert info is None


def test_upload_gets_info_from_upload():
    uploader = make_TestUploader(mock_cache=True)
    uploader._get_info_from_cache_mock.return_value = None
    uploader._upload_mock.return_value = {
        'url': 'http://foo.bar',
        'more': 'info',
    }
    image = uploader.upload('path/to/foo.png')
    assert uploader._get_info_from_cache_mock.call_args_list == [call('path/to/foo.png')]
    assert uploader._upload_mock.call_args_list == [call('path/to/foo.png')]
    assert uploader._store_info_to_cache_mock.call_args_list == [call(
        'path/to/foo.png',
        {'url': 'http://foo.bar', 'more': 'info'},
    )]
    assert isinstance(image, UploadedImage)
    assert image == 'http://foo.bar'
    assert image.more == 'info'

def test_upload_gets_info_from_cache():
    uploader = make_TestUploader(mock_cache=True)
    uploader._get_info_from_cache_mock.return_value = {
        'url': 'http://foo.bar',
        'more': 'info',
    }
    image = uploader.upload('path/to/foo.png')
    assert uploader._get_info_from_cache_mock.call_args_list == [call('path/to/foo.png')]
    assert uploader._upload_mock.call_args_list == []
    assert uploader._store_info_to_cache_mock.call_args_list == []
    assert isinstance(image, UploadedImage)
    assert image == 'http://foo.bar'
    assert image.more == 'info'

def test_upload_does_is_missing_url():
    uploader = make_TestUploader(mock_cache=True)
    uploader._get_info_from_cache_mock.return_value = None
    uploader._upload_mock.return_value = {
        'foo': 'http://foo.bar',
        'more': 'info',
    }
    info_str = repr(uploader._upload_mock.return_value)
    with pytest.raises(Exception, match=rf'^Missing "url" key in {re.escape(info_str)}$'):
        uploader.upload('path/to/foo.png')
