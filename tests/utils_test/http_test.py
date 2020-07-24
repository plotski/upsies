import asyncio
import itertools
import sys
from unittest.mock import call, patch

import aiohttp
import aiohttp.test_utils
import aiohttp.web
import pytest

from upsies import errors
from upsies.utils import http


@pytest.mark.asyncio
async def test_session_uses_separate_cookie_jar_per_domain():
    s1 = http._session('foo.com')
    s2 = http._session('bar.com')
    assert s1.cookie_jar is not s2.cookie_jar
    assert s1.cookie_jar is http._session('foo.com').cookie_jar
    assert s2.cookie_jar is http._session('bar.com').cookie_jar


@patch('upsies.utils.fs.tmpdir')
def test_cache_file_without_params(tmpdir_mock):
    tmpdir_mock.return_value = '/tmp/foo'
    url = 'http://localhost:123/foo/bar'
    exp_cache_file = '/tmp/foo/http:__localhost:123_foo_bar'
    assert http._cache_file(url) == exp_cache_file

@patch('upsies.utils.fs.tmpdir')
def test_cache_file_with_params(tmpdir_mock):
    tmpdir_mock.return_value = '/tmp/foo'
    url = 'http://localhost:123'
    params = {'foo': 'a b c', 'bar': 12}
    exp_cache_file = '/tmp/foo/http:__localhost:123?foo=a+b+c&bar=12'
    assert http._cache_file(url, params=params) == exp_cache_file


@patch('builtins.open')
def test_from_cache_cannot_read_cache_file(open_mock):
    open_mock.side_effect = OSError('Ouch')
    assert http._from_cache('mock/path') is None
    assert open_mock.call_args_list == [call('mock/path', 'r')]

@patch('builtins.open')
def test_from_cache_can_read_cache_file(open_mock):
    filehandle = open_mock.return_value.__enter__.return_value
    filehandle.read.return_value = 'cached data'
    assert http._from_cache('mock/path') == 'cached data'
    assert open_mock.call_args_list == [call('mock/path', 'r')]
    assert filehandle.read.call_args_list == [call()]


@patch('builtins.open')
def test_to_cache_cannot_write_cache_file(open_mock):
    filehandle = open_mock.return_value.__enter__.return_value
    filehandle.write.side_effect = OSError('No')
    with pytest.raises(RuntimeError, match=r'^Unable to write cache file mock/path: No$'):
        http._to_cache('mock/path', 'data')

@patch('builtins.open')
def test_to_cache_can_write_cache_file(open_mock):
    filehandle = open_mock.return_value.__enter__.return_value
    assert http._to_cache('mock/path', 'data') is None
    assert open_mock.call_args_list == [call('mock/path', 'w')]
    assert filehandle.write.call_args_list == [call('data')]


needs_python38 = pytest.mark.skipif(
    sys.version_info < (3, 8),
    reason='Requires AsyncMock from Python 3.8',
)

def _set_get_response(get_mock, text=None, json=None, side_effect=None):
    if side_effect:
        get_mock.return_value.__aenter__.return_value.text.side_effect = side_effect
        get_mock.return_value.__aenter__.return_value.json.side_effect = side_effect
    else:
        get_mock.return_value.__aenter__.return_value.text.return_value = text
        get_mock.return_value.__aenter__.return_value.json.return_value = json

@needs_python38
@pytest.mark.asyncio
@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@patch('aiohttp.ClientSession.get')
async def test_get_without_params(get_mock, from_cache_mock, to_cache_mock):
    _set_get_response(get_mock, text='response')
    assert await http.get('http://localhost:123/foo') == 'response'
    assert get_mock.call_args_list == [call('http://localhost:123/foo', params={})]
    assert from_cache_mock.call_args_list == []
    assert to_cache_mock.call_args_list == []

@needs_python38
@pytest.mark.asyncio
@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@patch('aiohttp.ClientSession.get')
async def test_get_with_params(get_mock, from_cache_mock, to_cache_mock):
    _set_get_response(get_mock, text='response')
    assert await http.get('http://localhost:123/foo', {'foo': 'bar'}) == 'response'
    assert get_mock.call_args_list == [call('http://localhost:123/foo',
                                            params={'foo': 'bar'})]
    assert from_cache_mock.call_args_list == []
    assert to_cache_mock.call_args_list == []


@needs_python38
@pytest.mark.asyncio
@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@patch('aiohttp.ClientSession.get')
async def test_get_handles_ClientResponseError(get_mock, from_cache_mock, to_cache_mock):
    _set_get_response(get_mock, side_effect=aiohttp.ClientResponseError(
        request_info=None,
        history=(),
        message='No response',
    ))
    with pytest.raises(errors.RequestError, match=r'^http://localhost:123/foo: No response$'):
        await http.get('http://localhost:123/foo')
    assert get_mock.call_args_list == [call('http://localhost:123/foo', params={})]

@needs_python38
@pytest.mark.asyncio
@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@patch('aiohttp.ClientSession.get')
async def test_get_handles_ClientConnectionError(get_mock, from_cache_mock, to_cache_mock):
    _set_get_response(get_mock, side_effect=aiohttp.ClientConnectionError('foo'))
    with pytest.raises(errors.RequestError, match=r'^http://localhost:123/foo: Failed to connect$'):
        await http.get('http://localhost:123/foo')
    assert get_mock.call_args_list == [call('http://localhost:123/foo', params={})]

@needs_python38
@pytest.mark.asyncio
@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@patch('aiohttp.ClientSession.get')
async def test_get_handles_ClientError(get_mock, from_cache_mock, to_cache_mock):
    _set_get_response(get_mock, side_effect=aiohttp.ClientError('Something'))
    with pytest.raises(errors.RequestError, match=r'^http://localhost:123/foo: Something$'):
        await http.get('http://localhost:123/foo')
    assert get_mock.call_args_list == [call('http://localhost:123/foo', params={})]


@needs_python38
@pytest.mark.asyncio
@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@patch('upsies.utils.http._cache_file')
@patch('aiohttp.ClientSession.get')
async def test_get_caches_response(get_mock, cache_file_mock, from_cache_mock, to_cache_mock):
    cache_file_mock.return_value = '/path/to/cachefile'
    from_cache_mock.return_value = None
    _set_get_response(get_mock, text='response')
    assert await http.get('http://localhost:123/foo', {'foo': 'bar'}, cache=True) == 'response'
    assert get_mock.call_args_list == [call('http://localhost:123/foo',
                                            params={'foo': 'bar'})]
    assert from_cache_mock.call_args_list == [call('/path/to/cachefile')]
    assert to_cache_mock.call_args_list == [call('/path/to/cachefile', 'response')]

@needs_python38
@pytest.mark.asyncio
@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@patch('upsies.utils.http._cache_file')
@patch('aiohttp.ClientSession.get')
async def test_get_returns_cached_response(get_mock, cache_file_mock, from_cache_mock, to_cache_mock):
    cache_file_mock.return_value = '/path/to/cachefile'
    from_cache_mock.return_value = 'response'
    _set_get_response(get_mock, text='response')
    assert await http.get('http://localhost:123/foo', {'foo': 'bar'}, cache=True) == 'response'
    assert get_mock.call_args_list == []
    assert from_cache_mock.call_args_list == [call('/path/to/cachefile')]
    assert to_cache_mock.call_args_list == []


@pytest.mark.asyncio
async def test_get_requests_multiple_concurrent_same_urls_only_once():

    class TestServer(aiohttp.test_utils.TestServer):
        def __init__(self):
            super().__init__(aiohttp.web.Application())
            self.requests_made = []
            self.app.router.add_route('get', '/x1', self.x1)
            self.app.router.add_route('get', '/x100', self.x100)

        def x1(self, request):
            self.requests_made.append(request)
            return aiohttp.web.Response(text='x1')

        def x100(self, request):
            self.requests_made.append(request)
            return aiohttp.web.Response(text='x100')

    async with TestServer() as srv:
        results = await asyncio.gather(*itertools.chain(
            (http.get(f'http://localhost:{srv.port}/x1', cache=True) for _ in range(10)),
            (http.get(f'http://localhost:{srv.port}/x100', cache=True),)
        ))
        assert {r.path for r in srv.requests_made} == {'/x1', '/x100'}
        assert len([x for x in results if x == 'x1']) == 10
        assert len([x for x in results if x == 'x100']) == 1
