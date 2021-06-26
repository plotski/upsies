import json
import re
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.http import Result
from upsies.utils.imghosts import ptpimg


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture(autouse=True)
def mock_url_base(mocker):
    mocker.patch('upsies.utils.imghosts.ptpimg.PtpimgImageHost._url_base', 'http://localhost:123')


@pytest.fixture
def make_imghost(tmp_path):
    def make_imghost(**kwargs):
        if 'cache_directory' not in kwargs:
            kwargs['cache_directory'] = tmp_path
        return ptpimg.PtpimgImageHost(**kwargs)

    return make_imghost


@pytest.mark.parametrize('apikey', ('', None, 0))
@pytest.mark.asyncio
async def test_upload_without_apikey(apikey, make_imghost, mocker):
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    imghost = make_imghost(apikey=apikey)
    with pytest.raises(errors.RequestError, match=r'^No API key configured$'):
        await imghost._upload('some/path.jpg')
    assert post_mock.call_args_list == []

@pytest.mark.asyncio
async def test_upload_succeeds(make_imghost, mocker):
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text='[{"code": "this_is_the_code", "ext": "png"}]',
        bytes=b'irrelevant',
    )))
    imghost = make_imghost(apikey='f00')
    image = await imghost._upload('some/path.jpg')
    assert image['url'] == imghost._url_base + '/this_is_the_code.png'
    assert post_mock.call_args_list == [call(
        url=f'{imghost._url_base}/upload.php',
        cache=False,
        headers={
            'referer': f'{imghost._url_base}/index.php',
        },
        data={
            'api_key': 'f00',
        },
        files={
            'file-upload[0]': 'some/path.jpg',
        },
    )]

@pytest.mark.asyncio
async def test_upload_gets_empty_list(make_imghost, mocker):
    mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text='[]',
        bytes=b'irrelevant',
    )))
    imghost = make_imghost(apikey='f00')
    with pytest.raises(RuntimeError, match=r'^Unexpected response: \[\]$'):
        await imghost._upload('some/path.jpg')

@pytest.mark.parametrize(
    argnames='json_response',
    argvalues=(
        'foo',
        123,
        [],
        [[]],
        [{}],
        [{'notcode': 'this_is_the_code', 'ext': 'png'}],
        [{'code': 'this_is_the_code', 'notext': 'png'}],
        [{'code': '', 'ext': 'png'}],
        [{'code': 'this_is_the_code', 'ext': ''}],
    ),
)
@pytest.mark.asyncio
async def test_upload_gets_unexpected_json(json_response, make_imghost, mocker):
    mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text=json.dumps(json_response),
        bytes=b'irrelevant',
    )))
    imghost = make_imghost(apikey='f00')
    with pytest.raises(RuntimeError, match=rf'^Unexpected response: {re.escape(str(json_response))}$'):
        await imghost._upload('some/path.jpg')
