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


def test_name():
    assert ptpimg.PtpimgImageHost.name == 'ptpimg'


def test_default_config():
    assert ptpimg.PtpimgImageHost.default_config == {
        'apikey': '',
        'base_url': 'https://ptpimg.me',
    }


@pytest.mark.parametrize('apikey', ('', None, 0))
@pytest.mark.asyncio
async def test_upload_without_apikey(apikey, mocker, tmp_path):
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    imghost = ptpimg.PtpimgImageHost(config={'apikey': apikey}, cache_directory=tmp_path)
    with pytest.raises(errors.RequestError, match=r'^Missing API key$'):
        await imghost._upload('some/path.jpg')
    assert post_mock.call_args_list == []

@pytest.mark.asyncio
async def test_upload_succeeds(mocker, tmp_path):
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text='[{"code": "this_is_the_code", "ext": "png"}]',
        bytes=b'irrelevant',
    )))
    imghost = ptpimg.PtpimgImageHost(config={'apikey': 'f00'}, cache_directory=tmp_path)
    image = await imghost._upload('some/path.jpg')
    assert image['url'] == imghost.config['base_url'] + '/this_is_the_code.png'
    assert post_mock.call_args_list == [call(
        url=f'{imghost.config["base_url"]}/upload.php',
        cache=False,
        headers={
            'referer': f'{imghost.config["base_url"]}/index.php',
        },
        data={
            'api_key': 'f00',
        },
        files={
            'file-upload[0]': 'some/path.jpg',
        },
    )]

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
async def test_upload_gets_unexpected_json(json_response, mocker, tmp_path):
    mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text=json.dumps(json_response),
        bytes=b'irrelevant',
    )))
    imghost = ptpimg.PtpimgImageHost(config={'apikey': 'f00'}, cache_directory=tmp_path)
    with pytest.raises(RuntimeError, match=rf'^Unexpected response: {re.escape(str(json_response))}$'):
        await imghost._upload('some/path.jpg')


@pytest.mark.asyncio
async def test_get_apikey_finds_apikey(mocker, tmp_path):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text=(
            '<html>'
            '<body>'
            '<form>'
            '<input id="api_key" name="api_key" value="d00d1e" />'
            '</form>'
            '</body>'
            '</html>'
        ),
        bytes=b'irrelevant',
    )))
    imghost = ptpimg.PtpimgImageHost(config={}, cache_directory=tmp_path)
    apikey = await imghost.get_apikey('foo@localhost', 'hunter2')
    assert apikey == 'd00d1e'
    assert post_mock.call_args_list == [call(
        url=f'{imghost.config["base_url"]}/login.php',
        cache=False,
        data={
            'email': 'foo@localhost',
            'pass': 'hunter2',
            'login': '',
        },
    )]
    assert get_mock.call_args_list == [call(f'{imghost.config["base_url"]}/logout.php')]

@pytest.mark.asyncio
async def test_get_apikey_when_request_fails(mocker, tmp_path):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(
        side_effect=errors.RequestError('no interwebs'),
    ))
    imghost = ptpimg.PtpimgImageHost(config={}, cache_directory=tmp_path)
    with pytest.raises(errors.RequestError, match=r'^no interwebs$'):
        await imghost.get_apikey('foo@localhost', 'hunter2')
    assert post_mock.call_args_list == [call(
        url=f'{imghost.config["base_url"]}/login.php',
        cache=False,
        data={
            'email': 'foo@localhost',
            'pass': 'hunter2',
            'login': '',
        },
    )]
    assert get_mock.call_args_list == []

@pytest.mark.asyncio
async def test_get_apikey_with_wrong_login(mocker, tmp_path):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text=(
            '<html>'
            ' <body>'
            '  <div class="container">'
            '   <div class="page-header">'
            '    <div class="panel panel-danger">'
            '     <div class="panel-heading">'
            '      <i class="glyphicon glyphicon-remove">'
            '      </i>'
            '      <span>'
            '       Error!'
            '      </span>'
            '     </div>'
            '     <div class="panel-body">'
            '      <ul>'
            '       <li>'
            '        Credentials are incorrect. Please try again.'
            '       </li>'
            '      </ul>'
            '     </div>'
            '    </div>'
            '   </div>'
            '  </div>'
            ' </body>'
            '</html>'
        ),
        bytes=b'irrelevant',
    )))
    imghost = ptpimg.PtpimgImageHost(config={}, cache_directory=tmp_path)
    with pytest.raises(errors.RequestError, match=r'^Credentials are incorrect\. Please try again\.$'):
        await imghost.get_apikey('foo@localhost', 'hunter2')
    assert post_mock.call_args_list == [call(
        url=f'{imghost.config["base_url"]}/login.php',
        cache=False,
        data={
            'email': 'foo@localhost',
            'pass': 'hunter2',
            'login': '',
        },
    )]
    assert get_mock.call_args_list == [call(f'{imghost.config["base_url"]}/logout.php')]

@pytest.mark.asyncio
async def test_get_apikey_fails_to_find_apikey(mocker, tmp_path):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(return_value=Result(
        text='',
        bytes=b'irrelevant',
    )))
    imghost = ptpimg.PtpimgImageHost(config={}, cache_directory=tmp_path)
    with pytest.raises(RuntimeError, match=r'^Failed to find API key$'):
        await imghost.get_apikey('foo@localhost', 'hunter2')
    assert post_mock.call_args_list == [call(
        url=f'{imghost.config["base_url"]}/login.php',
        cache=False,
        data={
            'email': 'foo@localhost',
            'pass': 'hunter2',
            'login': '',
        },
    )]
    assert get_mock.call_args_list == [call(f'{imghost.config["base_url"]}/logout.php')]
