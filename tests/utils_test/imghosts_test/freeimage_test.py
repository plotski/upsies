import json
import re
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.http import Result
from upsies.utils.imghosts import freeimage


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_name():
    assert freeimage.FreeimageImageHost.name == 'freeimage'


def test_default_config():
    assert freeimage.FreeimageImageHost.default_config == {
        **freeimage.FreeimageImageHost.default_config_common,
        **{
            'apikey': '6d207e02198a847aa98d0a2a901485a5',
            'base_url': 'https://freeimage.host',
        },
    }


@pytest.mark.asyncio
async def test_upload_image_succeeds(mocker, tmp_path):
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text='{"image":{"image":{"url":"https://localhost/path/to/image.png"}}}',
        bytes=b'irrelevant',
    )))
    imghost = freeimage.FreeimageImageHost(cache_directory=tmp_path)
    url = await imghost._upload_image('some/image.png')
    assert url == 'https://localhost/path/to/image.png'
    assert post_mock.call_args_list == [call(
        url=imghost.options['base_url'] + '/api/1/upload',
        cache=False,
        data={
            'key': imghost.options['apikey'],
            'action': 'upload',
            'format': 'json',
        },
        files={
            'source': 'some/image.png',
        },
    )]


@pytest.mark.parametrize(
    argnames='response',
    argvalues=(
        '{"image": {"image":{"ASDF":"https://foo/image.png"}}}',
        '{"image": {"ASDF":{"url":"https://foo/image.png"}}}',
        '{"ASDF": {"image":{"url":"https://foo/image.png"}}}',
    ),
)
@pytest.mark.asyncio
async def test_upload_image_gets_unexpected_response(response, mocker, tmp_path):
    mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text=response,
        bytes=b'irrelevant',
    )))
    imghost = freeimage.FreeimageImageHost(cache_directory=tmp_path)
    with pytest.raises(RuntimeError, match=rf'^Unexpected response: {re.escape(response)}$'):
        await imghost._upload_image('some/image.png')

@pytest.mark.asyncio
async def test_upload_image_gets_expected_error(mocker, tmp_path):
    mocker.patch('upsies.utils.http.post', AsyncMock(
        side_effect=errors.RequestError('ignored', text=json.dumps({
            "status_code": 400,
            "error": {
                "message": "Your request sucks",
                "code": 310,
                "context": "CHV\\UploadException"
            },
            "status_txt": "Bad Request"
        }))
    ))
    imghost = freeimage.FreeimageImageHost(cache_directory=tmp_path)
    with pytest.raises(errors.RequestError, match=r'^Bad Request: Your request sucks$'):
        await imghost._upload_image('some/image.png')

@pytest.mark.parametrize(
    argnames='error_text',
    argvalues=(
        [],
        '{invalid json]',
        '{"valid": "json", "with": "missing keys"}',
    ),
)
@pytest.mark.asyncio
async def test_upload_image_gets_unexpected_error(error_text, mocker, tmp_path):
    mocker.patch('upsies.utils.http.post', AsyncMock(
        side_effect=errors.RequestError('ignored', text=error_text),
    ))
    imghost = freeimage.FreeimageImageHost(cache_directory=tmp_path)
    with pytest.raises(errors.RequestError, match=rf'^Upload failed: {re.escape(str(error_text))}$'):
        await imghost._upload_image('some/image.png')
