import asyncio
import itertools
from unittest.mock import Mock, call, patch

import aiohttp
import aiohttp.test_utils
import aiohttp.web
import pytest

from upsies import errors
from upsies.utils import http


def run_async(awaitable):
    return asyncio.get_event_loop().run_until_complete(awaitable)


@pytest.mark.asyncio
async def test_session_uses_separate_cookie_jar_per_domain():
    s1 = http._session('foo.com')
    s2 = http._session('bar.com')
    assert s1.cookie_jar is not s2.cookie_jar
    assert s1.cookie_jar is http._session('foo.com').cookie_jar
    assert s2.cookie_jar is http._session('bar.com').cookie_jar


@patch('upsies.utils.fs.tmpdir')
@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_cache_file_without_params(tmpdir_mock, method):
    tmpdir_mock.return_value = '/tmp/foo'
    url = 'http://localhost:123/foo/bar'
    exp_cache_file = f'/tmp/foo/{method.upper()}.http:__localhost:123_foo_bar'
    assert http._cache_file(url, method) == exp_cache_file

@patch('upsies.utils.fs.tmpdir')
@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_cache_file_with_params(tmpdir_mock, method):
    tmpdir_mock.return_value = '/tmp/foo'
    url = 'http://localhost:123'
    params = {'foo': 'a b c', 'bar': 12}
    exp_cache_file = f'/tmp/foo/{method.upper()}.http:__localhost:123?foo=a+b+c&bar=12'
    assert http._cache_file(url, method, params=params) == exp_cache_file

@patch('upsies.utils.fs.tmpdir')
@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_cache_file_with_very_long_params(tmpdir_mock, method):
    tmpdir_mock.return_value = '/tmp/foo'
    url = 'http://localhost:123'
    params = {'foo': 'a b c ' * 100, 'bar': 12}
    exp_cache_file = (
        f'/tmp/foo/{method.upper()}.http:__localhost:123?'
        f'[HASH:{http._semantic_hash(params)}]'
    )
    assert http._cache_file(url, method, params=params) == exp_cache_file


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


def _set_request_response(request_mock, text=None, json=None, side_effect=None):
    if side_effect:
        request_mock.return_value.__aenter__.return_value.text.side_effect = side_effect
        request_mock.return_value.__aenter__.return_value.json.side_effect = side_effect
    else:
        request_mock.return_value.__aenter__.return_value.text.return_value = text
        request_mock.return_value.__aenter__.return_value.json.return_value = json

@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_request_without_params(from_cache_mock, to_cache_mock, method):
    with patch(f'aiohttp.ClientSession.{method.lower()}') as request_mock:
        _set_request_response(request_mock, text='response')
        assert run_async(http._request(method, 'http://localhost:123/foo')) == 'response'
        assert request_mock.call_args_list == [call('http://localhost:123/foo', params={})]
        assert from_cache_mock.call_args_list == []
        assert to_cache_mock.call_args_list == []

@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_request_with_params(from_cache_mock, to_cache_mock, method):
    with patch(f'aiohttp.ClientSession.{method.lower()}') as request_mock:
        _set_request_response(request_mock, text='response')
        assert run_async(http._request(method, 'http://localhost:123/foo', {'foo': 'bar'})) == 'response'
        assert request_mock.call_args_list == [call('http://localhost:123/foo',
                                                    params={'foo': 'bar'})]
        assert from_cache_mock.call_args_list == []
        assert to_cache_mock.call_args_list == []

@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_request_handles_ClientResponseError(from_cache_mock, to_cache_mock, method):
    with patch(f'aiohttp.ClientSession.{method.lower()}') as request_mock:
        _set_request_response(request_mock, side_effect=aiohttp.ClientResponseError(
            request_info=None,
            history=(),
            message='No response',
        ))
        with pytest.raises(errors.RequestError, match=r'^http://localhost:123/foo: No response$'):
            run_async(http._request(method, 'http://localhost:123/foo'))
        assert request_mock.call_args_list == [call('http://localhost:123/foo', params={})]

@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_request_handles_ClientConnectionError(from_cache_mock, to_cache_mock, method):
    with patch(f'aiohttp.ClientSession.{method.lower()}') as request_mock:
        _set_request_response(request_mock, side_effect=aiohttp.ClientConnectionError('foo'))
        with pytest.raises(errors.RequestError, match=r'^http://localhost:123/foo: foo$'):
            run_async(http._request(method, 'http://localhost:123/foo'))
        assert request_mock.call_args_list == [call('http://localhost:123/foo', params={})]

@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_request_handles_ClientError(from_cache_mock, to_cache_mock, method):
    with patch(f'aiohttp.ClientSession.{method.lower()}') as request_mock:
        _set_request_response(request_mock, side_effect=aiohttp.ClientError('Something'))
        with pytest.raises(errors.RequestError, match=r'^http://localhost:123/foo: Something$'):
            run_async(http._request(method, 'http://localhost:123/foo'))
        assert request_mock.call_args_list == [call('http://localhost:123/foo', params={})]

@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@patch('upsies.utils.http._cache_file')
@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_request_caches_response(cache_file_mock, from_cache_mock, to_cache_mock, method):
    with patch(f'aiohttp.ClientSession.{method.lower()}') as request_mock:
        cache_file_mock.return_value = '/path/to/cachefile'
        from_cache_mock.return_value = None
        _set_request_response(request_mock, text='response')
        assert run_async(http._request(method, 'http://localhost:123/foo', {'foo': 'bar'}, cache=True)) == 'response'
        assert request_mock.call_args_list == [call('http://localhost:123/foo',
                                                    params={'foo': 'bar'})]
        assert from_cache_mock.call_args_list == [call('/path/to/cachefile')]
        assert to_cache_mock.call_args_list == [call('/path/to/cachefile', 'response')]

@patch('upsies.utils.http._to_cache')
@patch('upsies.utils.http._from_cache')
@patch('upsies.utils.http._cache_file')
@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_request_returns_cached_response(cache_file_mock, from_cache_mock, to_cache_mock, method):
    with patch(f'aiohttp.ClientSession.{method.lower()}') as request_mock:
        cache_file_mock.return_value = '/path/to/cachefile'
        from_cache_mock.return_value = 'response'
        _set_request_response(request_mock, text='response')
        assert run_async(http._request(method, 'http://localhost:123/foo', {'foo': 'bar'}, cache=True)) == 'response'
        assert request_mock.call_args_list == []
        assert from_cache_mock.call_args_list == [call('/path/to/cachefile')]
        assert to_cache_mock.call_args_list == []

@pytest.mark.asyncio
@pytest.mark.parametrize('method', ('GET', 'POST'))
async def test_requesting_identical_requests_performs_only_one_while_the_others_block(method):
    class TestServer(aiohttp.test_utils.TestServer):
        def __init__(self, method):
            super().__init__(aiohttp.web.Application())
            self.requests_made = []
            self.app.router.add_route(method, '/x1', self.x1)
            self.app.router.add_route(method, '/x100', self.x100)

        def x1(self, request):
            self.requests_made.append(request)
            return aiohttp.web.Response(text='x1')

        def x100(self, request):
            self.requests_made.append(request)
            return aiohttp.web.Response(text='x100')

    async with TestServer(method=method) as srv:
        results = await asyncio.gather(*itertools.chain(
            (http._request(method, f'http://localhost:{srv.port}/x1', cache=True) for _ in range(10)),
            (http._request(method, f'http://localhost:{srv.port}/x100', cache=True),)
        ))
        assert {r.path for r in srv.requests_made} == {'/x1', '/x100'}
        assert len([x for x in results if x == 'x1']) == 10
        assert len([x for x in results if x == 'x100']) == 1


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

@patch('upsies.utils.http._request', new_callable=AsyncMock)
def test_get_forwards_arguments_to_request(request_mock):
    asyncio.get_event_loop().run_until_complete(
        http.get('http://localhost:123/foo', {'foo': 'bar'}, cache=True),
    )
    assert request_mock.call_args_list == [
        call('GET', 'http://localhost:123/foo', params={'foo': 'bar'}, cache=True),
    ]

@patch('upsies.utils.http._request', new_callable=AsyncMock)
def test_post_forwards_arguments_to_request(request_mock):
    asyncio.get_event_loop().run_until_complete(
        http.post('http://localhost:123/foo', {'foo': 'bar'}, cache=True),
    )
    assert request_mock.call_args_list == [
        call('POST', 'http://localhost:123/foo', params={'foo': 'bar'}, cache=True),
    ]
