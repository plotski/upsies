import json
import re
from unittest.mock import AsyncMock, Mock, call

import pytest

from upsies import __project_name__, constants, errors
from upsies.utils import fs
from upsies.utils.http import Result
from upsies.utils.imghosts import imgbb


def test_name():
    assert imgbb.ImgbbImageHost.name == 'imgbb'


def test_default_config():
    assert imgbb.ImgbbImageHost.default_config == {
        **imgbb.ImgbbImageHost.default_config_common,
        **{
            'base_url': 'https://api.imgbb.com',
            'apikey': '',
        },
    }


def test_description():
    assert imgbb.ImgbbImageHost.description == (
        'You need an API key to upload images. You can get one by following these steps:\n'
        '\n'
        '  1. Create an account: https://imgbb.com/signup\n'
        '  2. Go to https://api.imgbb.com/ and click on "Get API key".\n'
        f'  3. Store your API key in {fs.tildify_path(constants.IMGHOSTS_FILEPATH)}:\n'
        '\n'
        f'       $ {__project_name__} set imghosts.imgbb.apikey <YOUR API KEY>'
    )


@pytest.mark.asyncio
async def test_upload_image_succeeds(mocker, tmp_path):
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text='{"data":{"url":"https://localhost/path/to/image.png"}}',
        bytes=b'irrelevant',
    )))
    imghost = imgbb.ImgbbImageHost(cache_directory=tmp_path)
    url = await imghost._upload_image('some/image.png')
    assert url == 'https://localhost/path/to/image.png'
    assert post_mock.call_args_list == [call(
        url=imghost.options['base_url'] + '/1/upload',
        cache=False,
        data={
            'key': imghost.options['apikey'],
        },
        files={
            'image': 'some/image.png',
        },
    )]


@pytest.mark.parametrize(
    argnames='response',
    argvalues=(
        '{"data":{"ASDF":"https://some/image.png"}}',
        '{"ASDF":{"url":"https://some/image.png"}}',
    ),
)
@pytest.mark.asyncio
async def test_upload_image_gets_unexpected_response(response, mocker, tmp_path):
    mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text=response,
        bytes=b'irrelevant',
    )))
    imghost = imgbb.ImgbbImageHost(cache_directory=tmp_path)
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
    imghost = imgbb.ImgbbImageHost(cache_directory=tmp_path)
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
    imghost = imgbb.ImgbbImageHost(cache_directory=tmp_path)
    with pytest.raises(errors.RequestError, match=rf'^Upload failed: {re.escape(str(error_text))}$'):
        await imghost._upload_image('some/image.png')
