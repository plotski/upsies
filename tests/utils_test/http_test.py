import asyncio
import base64
import hashlib
import io
import itertools
import os
import re
import time
from unittest.mock import Mock, call

import httpx
import pytest
from pytest_httpserver.httpserver import Response

from upsies import __project_name__, __version__, errors
from upsies.utils import http


@pytest.fixture(autouse=True)
def clear_global_client_cookies():
    http._client.cookies.clear()


@pytest.fixture
def mock_cache(mocker):
    parent = Mock(
        cache_file=Mock(return_value='path/to/cache.file'),
        from_cache=Mock(return_value=None),
        to_cache=Mock(return_value=None),
    )
    mocker.patch('upsies.utils.http._cache_file', parent.cache_file)
    mocker.patch('upsies.utils.http._from_cache', parent.from_cache)
    mocker.patch('upsies.utils.http._to_cache', parent.to_cache)
    yield parent


class RequestHandler:
    def __init__(self):
        self.requests_seen = []

    def __call__(self, request):
        # `request` is a Request object from werkzeug
        # https://werkzeug.palletsprojects.com/en/1.0.x/wrappers/#werkzeug.wrappers.BaseRequest
        try:
            return self.handle(request)
        except Exception as e:
            # pytest-httpserver doesn't show the traceback if we call
            # raise_for_status() on the response.
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
            raise

    def handle(self, request):
        raise NotImplementedError()


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.mark.parametrize(
    argnames=('auth', 'cache', 'max_cache_age', 'user_agent', 'follow_redirects', 'timeout', 'cookies'),
    argvalues=(
        (None, False, 123, False, True, 1, 'mock cookies a'),
        (('foo', 'bar'), False, 456, True, False, 2, 'mock cookies b'),
        (('bar', 'foo'), True, 789, False, True, 3, 'mock cookies c'),
        (None, True, 0, True, False, 4, 'mock cookies d'),
    ),
)
@pytest.mark.asyncio
async def test_get_forwards_arguments_to_request(auth, cache, max_cache_age, user_agent, follow_redirects, timeout, cookies, mocker):
    request_mock = mocker.patch('upsies.utils.http._request', new_callable=AsyncMock)
    result = await http.get(
        url='http://localhost:123/foo',
        headers={'foo': 'bar'},
        params={'bar': 'baz'},
        auth=auth,
        cache=cache,
        max_cache_age=max_cache_age,
        user_agent=user_agent,
        follow_redirects=follow_redirects,
        timeout=timeout,
        cookies=cookies,
    )
    assert request_mock.call_args_list == [
        call(
            method='GET',
            url='http://localhost:123/foo',
            headers={'foo': 'bar'},
            params={'bar': 'baz'},
            auth=auth,
            cache=cache,
            max_cache_age=max_cache_age,
            user_agent=user_agent,
            follow_redirects=follow_redirects,
            timeout=timeout,
            cookies=cookies,
        )
    ]
    assert result is request_mock.return_value

@pytest.mark.parametrize(
    argnames=('auth', 'cache', 'max_cache_age', 'user_agent', 'follow_redirects', 'timeout', 'cookies'),
    argvalues=(
        (('a', 'b'), False, 0, False, False, 10, 'mock cookies A'),
        (None, False, 123, True, False, 20, 'mock cookies B'),
        (('b', 'a'), True, 456, False, True, 30, 'mock cookies C'),
        (None, True, 789, True, True, 40, 'mock cookies D'),
    ),
)
@pytest.mark.asyncio
async def test_post_forwards_arguments_to_request(auth, cache, max_cache_age, user_agent, follow_redirects, timeout, cookies, mocker):
    request_mock = mocker.patch('upsies.utils.http._request', new_callable=AsyncMock)
    result = await http.post(
        url='http://localhost:123/foo',
        headers={'foo': 'bar'},
        data=b'foo',
        files=b'bar',
        auth=auth,
        cache=cache,
        max_cache_age=max_cache_age,
        user_agent=user_agent,
        follow_redirects=follow_redirects,
        timeout=timeout,
        cookies=cookies,
    )
    assert request_mock.call_args_list == [
        call(
            method='POST',
            url='http://localhost:123/foo',
            headers={'foo': 'bar'},
            data=b'foo',
            files=b'bar',
            auth=auth,
            cache=cache,
            max_cache_age=max_cache_age,
            user_agent=user_agent,
            follow_redirects=follow_redirects,
            timeout=timeout,
            cookies=cookies,
        )
    ]
    assert result is request_mock.return_value


def test_Result_is_string():
    r = http.Result('foo', b'foo')
    assert isinstance(r, str)
    assert r == 'foo'

def test_Result_bytes():
    r = http.Result('föö', bytes('föö', 'utf-8'))
    assert r.bytes == bytes('föö', 'utf-8')
    assert str(r.bytes, 'utf-8') == 'föö'

def test_Result_headers():
    r = http.Result('foo', b'foo')
    assert r.headers == {}
    r = http.Result('foo', b'foo', headers={'a': '1', 'b': '2'})
    assert r.headers == {'a': '1', 'b': '2'}

def test_Result_status_code():
    r = http.Result('foo', b'foo')
    assert r.status_code is None
    r = http.Result('foo', b'foo', status_code=304)
    assert r.status_code == 304

def test_Result_json():
    r = http.Result('{"this":"that"}', b'{"this":"that"}')
    assert r.json() == {'this': 'that'}
    r = http.Result('{"this":"that"', b'{"this":"that"')
    assert r == '{"this":"that"'
    with pytest.raises(errors.RequestError, match=r'^Malformed JSON: {"this":"that": '):
        r.json()

@pytest.mark.parametrize(
    argnames='kwargs, exp_kwargs',
    argvalues=(
        ({'text': 'föö', 'bytes': bytes('föö', 'utf-8')}, {'text': 'föö', 'bytes': bytes('föö', 'utf-8')}),
        ({'text': 'foo', 'bytes': b'foo', 'headers': {'bar': 'baz'}}, {'text': 'foo', 'bytes': b'foo', 'headers': {'bar': 'baz'}}),
        ({'text': 'foo', 'bytes': b'foo', 'headers': {}}, {'text': 'foo', 'bytes': b'foo'}),
        ({'text': 'foo', 'bytes': b'foo', 'headers': None}, {'text': 'foo', 'bytes': b'foo'}),
        ({'text': 'foo', 'bytes': b'foo', 'status_code': 123}, {'text': 'foo', 'bytes': b'foo', 'status_code': 123}),
        ({'text': 'foo', 'bytes': b'foo', 'status_code': 0}, {'text': 'foo', 'bytes': b'foo', 'status_code': 0}),
        ({'text': 'foo', 'bytes': b'foo', 'status_code': None}, {'text': 'foo', 'bytes': b'foo'}),
    ),
    ids=lambda v: str(v),
)
def test_Result_repr(kwargs, exp_kwargs):
    r = http.Result(**kwargs)
    exp_kwargs_string = ', '.join(f'{k}={v!r}' for k, v in exp_kwargs.items())
    assert repr(r) == f'Result({exp_kwargs_string})'


@pytest.mark.asyncio
async def test_request_with_invalid_url(mock_cache):
    # The error message keeps changing, so we just make sure RequestError is raised
    url = r'http:///baz'
    with pytest.raises(errors.RequestError, match=(rf"^{re.escape(url)}: ")) as excinfo:
        await http._request('GET', url)
    assert excinfo.value.status_code is None

@pytest.mark.asyncio
async def test_request_with_invalid_method(mock_cache):
    with pytest.raises(ValueError, match=r'^Invalid method: hello$'):
        await http._request('hello', 'asdf')


@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_with_caching_disabled(method, mock_cache, httpserver):
    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_data(
        'have this',
    )
    for i in range(3):
        result = await http._request(
            method=method,
            url=httpserver.url_for('/foo'),
            cache=False,
        )
        assert result == 'have this'
        assert isinstance(result, http.Result)
        assert mock_cache.mock_calls == []

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_gets_cached_result(method, mock_cache):
    mock_cache.from_cache.return_value = 'cached result'
    url = 'http://localhost:12345/foo'
    for i in range(1, 4):
        result = await http._request(method=method, url=url, cache=True)
        assert result == 'cached result'
        assert result is mock_cache.from_cache.return_value
        assert mock_cache.mock_calls == [
            call.cache_file(method, url, {}),
            call.from_cache(mock_cache.cache_file.return_value, max_age=float('inf')),
        ] * i

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_caches_result(method, mock_cache, httpserver):
    mock_cache.from_cache.return_value = None
    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_data(
        'have this',
    )
    result = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        cache=True,
    )
    assert result == 'have this'
    assert isinstance(result, http.Result)
    assert mock_cache.mock_calls == [
        call.cache_file(method, httpserver.url_for('/foo'), {}),
        call.from_cache(mock_cache.cache_file.return_value, max_age=float('inf')),
        call.cache_file(method, httpserver.url_for('/foo'), {}),
        call.to_cache(mock_cache.cache_file.return_value, b'have this'),
    ]


@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_sends_default_headers(method, mock_cache, httpserver):
    class Handler(RequestHandler):
        def handle(self, request):
            for k, v in http._default_headers.items():
                assert request.headers[k] == v
            return Response('have this')

    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        Handler(),
    )
    result = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        user_agent=True,
    )
    assert result == 'have this'
    assert isinstance(result, http.Result)

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_sends_custom_headers(method, mock_cache, httpserver, mocker):
    mocker.patch.dict(http._default_headers, {'a': '1', 'b': '2'})
    custom_headers = {'foo': 'bar', 'b': '20'}
    combined_headers = {'a': '1', 'b': '20', 'foo': 'bar'}

    class Handler(RequestHandler):
        def handle(self, request):
            for k, v in combined_headers.items():
                assert request.headers[k] == v
            return Response('have this')

    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        Handler(),
    )
    result = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        headers=custom_headers,
    )
    assert result == 'have this'
    assert isinstance(result, http.Result)

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_sends_params(method, mock_cache, httpserver):
    query = {'foo': '1', 'bar': 'baz'}
    httpserver.expect_request(
        uri='/foo',
        method=method,
        query_string=query,
    ).respond_with_data(
        'have this',
    )
    result = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        params=query,
    )
    assert result == 'have this'
    assert isinstance(result, http.Result)

@pytest.mark.parametrize('data', (b'raw bytes', 'string'))
@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_sends_data(method, data, mock_cache, httpserver):
    httpserver.expect_request(
        uri='/foo',
        method=method,
        data=data,
    ).respond_with_data(
        'have this',
    )
    result = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        data=data,
    )
    assert result == 'have this'
    assert isinstance(result, http.Result)

@pytest.mark.asyncio
async def test_request_sends_files(mock_cache, httpserver, mocker):
    files = {
        'foo': 'path/to/foo.jpg',
        'bar': ('path/to/bar', 'image/png'),
    }
    mocker.patch('upsies.utils.http._open_files', return_value={
        'foo': ('foo.jpg', io.BytesIO(b'foo image')),
        'bar': ('bar', io.BytesIO(b'bar image'), 'image/png')
    })

    class Handler(RequestHandler):
        def handle(self, request):
            assert request.content_type.startswith('multipart/form-data')
            data = request.data.decode('utf-8')
            assert re.search(
                (
                    r'^'
                    r'--[0-9a-f]{32}\r\n'
                    r'Content-Disposition: form-data; name="foo"; filename="foo.jpg"\r\n'
                    r'Content-Type: image/jpeg\r\n'
                    r'\r\n'
                    r'foo image\r\n'
                    r'--[0-9a-f]{32}\r\n'
                    r'Content-Disposition: form-data; name="bar"; filename="bar"\r\n'
                    r'Content-Type: image/png\r\n'
                    r'\r\n'
                    r'bar image\r\n'
                    r'--[0-9a-f]{32}--\r\n'
                    r'$'
                ),
                data,
            )
            return Response('have this')

    httpserver.expect_request(
        uri='/foo',
        method='POST',
    ).respond_with_handler(
        Handler(),
    )
    result = await http._request(
        method='POST',
        url=httpserver.url_for('/foo'),
        files=files,
    )
    assert result == 'have this'
    assert isinstance(result, http.Result)

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_sends_auth(method, mock_cache, httpserver):
    auth = ('AzureDiamond', 'hunter2')
    auth_str = ':'.join(auth)
    auth_encoded = base64.b64encode(auth_str.encode('utf-8')).decode()

    class Handler(RequestHandler):
        def handle(self, request):
            assert request.headers['Authorization'] == f'Basic {auth_encoded}'
            return Response('have this')

    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        Handler(),
    )
    result = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        auth=auth,
    )
    assert result == 'have this'
    assert isinstance(result, http.Result)

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_does_not_send_auth(method, mock_cache, httpserver):
    class Handler(RequestHandler):
        def handle(self, request):
            assert request.headers.get('Authorization') is None
            return Response('have this')

    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        Handler(),
    )
    result = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        auth=None,
    )
    assert result == 'have this'
    assert isinstance(result, http.Result)

@pytest.mark.parametrize(
    argnames='user_agent, exp_user_agent',
    argvalues=(
        (True, f'{__project_name__}/{__version__}'),
        (False, None),
        ('Mozilla/5.0 (compatible; MSIE 8.0; Windows NT 6.3; Win64; x64)',
         'Mozilla/5.0 (compatible; MSIE 8.0; Windows NT 6.3; Win64; x64)'),
    ),
)
@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_sends_user_agent(method, user_agent, exp_user_agent, mock_cache, httpserver):
    class Handler(RequestHandler):
        def handle(self, request):
            assert request.headers.get('User-Agent') == exp_user_agent
            return Response('have this')

    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        Handler(),
    )
    result = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        user_agent=user_agent,
    )
    assert result == 'have this'
    assert isinstance(result, http.Result)

@pytest.mark.parametrize(
    argnames='timeout, response_delay, exp_exception',
    argvalues=(
        (1, 0.5, None),
        (1, 1.5, errors.RequestError('timeout')),
    ),
)
@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_with_timeout_argument(method, timeout, response_delay, exp_exception, mock_cache, httpserver):
    class Handler(RequestHandler):
        def handle(self, request):
            import time
            time.sleep(response_delay)
            return Response('have this')

    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        Handler(),
    )
    request_url = httpserver.url_for('/foo')
    if exp_exception:
        with pytest.raises(errors.RequestError, match=rf'^{request_url}: Timeout$'):
            await http._request(
                method=method,
                url=request_url,
                timeout=timeout,
            )
    else:
        result = await http._request(
            method=method,
            url=request_url,
            timeout=timeout,
        )
        assert result == 'have this'
        assert isinstance(result, http.Result)

@pytest.mark.parametrize('follow_redirects', (True, False))
@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.parametrize('status_code', (301, 302, 303, 307, 308))
@pytest.mark.asyncio
async def test_request_with_follow_redirects(status_code, method, follow_redirects, mock_cache, httpserver):
    class Handler(RequestHandler):
        def handle(self, request):
            if request.path == '/foo':
                return Response(
                    response='not redirected',
                    status=status_code,
                    headers={'Location': httpserver.url_for('/bar')},
                )
            else:
                return Response('redirected')

    handler = Handler()
    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        handler,
    )
    httpserver.expect_request(
        uri='/bar',
        method='GET' if status_code in (301, 302, 303) else method,
    ).respond_with_handler(
        handler,
    )

    result = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        follow_redirects=follow_redirects,
    )
    if follow_redirects:
        assert result == 'redirected'
    else:
        assert result == 'not redirected'
    assert isinstance(result, http.Result)

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_preserves_session_cookies_between_requests(method, mock_cache, httpserver):
    class Handler(RequestHandler):
        def handle(self, request):
            from werkzeug.datastructures import ImmutableMultiDict
            request_cookies = getattr(self, 'request_cookies', ImmutableMultiDict())
            assert request.cookies == request_cookies

            bar = int(request_cookies.get('bar', 0))
            self.request_cookies = ImmutableMultiDict({'bar': str(bar + 1)})

            if request_cookies:
                headers = {'Set-Cookie': f'bar={bar + 1}'}
            else:
                headers = {'Set-Cookie': 'bar=1'}

            return Response(response=f'bar is currently {bar}', headers=headers)

    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        Handler(),
    )

    for i in range(3):
        response = await http._request(
            method=method,
            url=httpserver.url_for('/foo'),
            cache=False,
        )
        assert response == f'bar is currently {i}'


@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_uses_separate_cookie_jar_per_domain(method, mock_cache, httpserver):
    class Handler(RequestHandler):
        def handle(self, request):
            if getattr(self, 'set_cookie'):
                domain = request.url.split('/')[2]
                headers = {'Set-Cookie': f'cookie_domain={domain}'}
            else:
                headers = {}
            return Response(
                response='current cookies: ' + ', '.join(f'{k}={v}' for k, v in request.cookies.items()),
                headers=headers,
            )

    handler = Handler()
    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        handler,
    )

    hosts = ('foo.localhost', 'bar.localhost', 'baz.localhost')

    # Fill cookie jar with some subdomain-specific cookies
    handler.set_cookie = True
    for host in hosts:
        httpserver.host = host
        response = await http._request(
            method=method,
            url=httpserver.url_for('/foo'),
            cache=False,
        )
        assert response == 'current cookies: '

    # Check if we get the same cookies back for each subdomain
    handler.set_cookie = False
    for host in hosts:
        httpserver.host = host
        response = await http._request(
            method=method,
            url=httpserver.url_for('/foo'),
            cache=False,
        )
        assert response == f'current cookies: cookie_domain={host}:{httpserver.port}'

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_with_custom_cookies(method, mock_cache, httpserver):
    custom_cookies = {'foo': 'bar'}
    server_cookies = {'server': 'cookie'}

    class Handler(RequestHandler):
        def handle(self, request):
            from werkzeug.datastructures import ImmutableMultiDict
            if getattr(self, 'cookies_already_set', False):
                headers = {}
                exp_request_cookies = ImmutableMultiDict({**custom_cookies, **server_cookies})
            else:
                headers = {'Set-Cookie': ', '.join(f'{k}={v}' for k, v in server_cookies.items())}
                self.cookies_already_set = True
                exp_request_cookies = ImmutableMultiDict(custom_cookies)

            assert request.cookies == exp_request_cookies

            return Response(
                response='got cookies: ' + ', '.join(f'{k}={v}' for k, v in request.cookies.items()),
                headers=headers,
            )

    handler = Handler()
    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        handler,
    )

    response = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        cache=False,
        cookies=custom_cookies,
    )
    assert response == 'got cookies: ' + ', '.join(f'{k}={v}' for k, v in custom_cookies.items())

    response = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        cache=False,
        cookies=custom_cookies,
    )
    assert response == 'got cookies: ' + ', '.join(f'{k}={v}' for k, v in {**custom_cookies, **server_cookies}.items())

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_with_cookies_file(method, mock_cache, httpserver, tmp_path):
    cookies_filepath = str(tmp_path / 'my.cookies')

    class Handler(RequestHandler):
        def handle(self, request):
            from werkzeug.datastructures import ImmutableMultiDict
            assert request.cookies == ImmutableMultiDict(self.expected_cookies)

            if getattr(self, 'set_cookie'):
                subdomain = request.url.split('/')[2].split('.')[0]
                headers = {'Set-Cookie': f'your_cookie={subdomain}; max-age=500000'}
            else:
                headers = {}
            domain = request.url.split('/')[2]
            return Response(
                response=f'got cookies on {domain}: ' + ', '.join(f'{k}={v}' for k, v in request.cookies.items()),
                headers=headers,
            )

    handler = Handler()
    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        handler,
    )

    for subdomain in ('foo', 'bar'):
        httpserver.host = f'{subdomain}.localhost'
        handler.set_cookie = True
        handler.expected_cookies = {}
        response = await http._request(
            method=method,
            url=httpserver.url_for('/foo'),
            cache=False,
            cookies=cookies_filepath + f'.{subdomain}',
        )
        assert response == f'got cookies on {subdomain}.localhost:{httpserver.port}: '

    # Remove in-memory cookies; only send cookies from file
    http._client.cookies.clear()

    for subdomain in ('foo', 'bar'):
        httpserver.host = f'{subdomain}.localhost'
        handler.set_cookie = False
        handler.expected_cookies = {'your_cookie': subdomain}
        response = await http._request(
            method=method,
            url=httpserver.url_for('/foo'),
            cache=False,
            cookies=cookies_filepath + f'.{subdomain}',
        )
        assert response == f'got cookies on {subdomain}.localhost:{httpserver.port}: your_cookie={subdomain}'

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_with_unsavable_cookies_file(method, mock_cache, httpserver, tmp_path):
    class Handler(RequestHandler):
        def handle(self, request):
            headers = {'Set-Cookie': 'your_cookie=foo; max-age=500000'}
            return Response(
                response='setting cookie',
                headers=headers,
            )

    handler = Handler()
    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_handler(
        handler,
    )

    cookies_filepath = str(tmp_path / 'no' / 'such' / 'directory' / 'my.cookies')
    httpserver.host = 'foo.localhost'
    with pytest.raises(errors.RequestError, match=rf'^Failed to write {cookies_filepath}: No such file or directory$'):
        await http._request(
            method=method,
            url=httpserver.url_for('/foo'),
            cache=False,
            cookies=cookies_filepath,
        )

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_with_unloadable_cookies_file(method, mock_cache, tmp_path):
    cookies_filepath = tmp_path / 'my.cookies'
    cookies_filepath.write_text('mock cookies')
    cookies_filepath.chmod(0o000)
    try:
        with pytest.raises(errors.RequestError, match=rf'^Failed to read {cookies_filepath}: Permission denied$'):
            await http._request(
                method=method,
                url='http://localhost:123/foo',
                cache=False,
                cookies=cookies_filepath,
            )
    finally:
        cookies_filepath.chmod(0o600)

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_with_unsupported_cookies_type(method, mock_cache):
    with pytest.raises(RuntimeError, match=r'^Unsupported cookies type: \(1, 2, 3\)$'):
        await http._request(
            method=method,
            url='http://localhost:123/foo',
            cache=False,
            cookies=(1, 2, 3),
        )

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_catches_HTTP_error_status(method, mock_cache, httpserver):
    url = httpserver.url_for('/foo')
    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_data(
        '<html>  Dave is not   here\n</html> ',
        status=404,
        headers={'foo': 'bar'},
    )
    with pytest.raises(errors.RequestError, match=rf'^{url}: Dave is not here$') as excinfo:
        await http._request(method=method, url=url)
    assert excinfo.value.status_code == 404
    assert excinfo.value.headers['foo'] == 'bar'
    assert excinfo.value.url == url
    assert excinfo.value.text == '<html>  Dave is not   here\n</html> '


@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_catches_NetworkError(method, mock_cache):
    url = 'http://127.0.0.1:12345/foo/bar/baz'
    with pytest.raises(errors.RequestError, match=rf'^{url}: All connection attempts failed$') as excinfo:
        await http._request(method=method, url=url)
    assert excinfo.value.status_code is None
    assert excinfo.value.headers == {}

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_catches_TimeoutException(method, mock_cache, mocker):
    exc = httpx.TimeoutException(
        message='Some error',
        request='mock request',
    )
    mocker.patch.object(http._client, 'send', AsyncMock(side_effect=exc))
    url = 'http://localhost:12345/foo/bar/baz'
    with pytest.raises(errors.RequestError, match=rf'^{url}: Timeout$') as excinfo:
        await http._request(method=method, url=url)
    assert excinfo.value.status_code is None
    assert excinfo.value.headers == {}

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_catches_HTTPError(method, mock_cache, mocker):
    exc = httpx.HTTPError('Some error')
    mocker.patch.object(http._client, 'send', AsyncMock(side_effect=exc))
    url = 'http://localhost:12345/foo/bar/baz'
    with pytest.raises(errors.RequestError, match=rf'^{url}: Some error$') as excinfo:
        await http._request(method=method, url=url)
    assert excinfo.value.status_code is None
    assert excinfo.value.headers == {}


@pytest.mark.asyncio
async def test_get_performs_only_one_identical_request_at_the_same_time(httpserver, mocker, tmp_path):
    mocker.patch.object(http, 'cache_directory', str(tmp_path))

    class Handler(RequestHandler):
        def handle(self, request):
            self.requests_seen.append(request.full_path)
            return Response(request.full_path)

    handler = Handler()
    for path in ('/a', '/b', '/c', '/d'):
        httpserver.expect_request(
            uri=path,
            method='GET',
        ).respond_with_handler(
            handler,
        )

    coros = tuple(itertools.chain(
        (http.get(httpserver.url_for('/a'), cache=True) for _ in range(10)),
        (http.get(httpserver.url_for('/b'), cache=True) for _ in range(5)),
        (http.get(httpserver.url_for('/c'), params={'foo': '1'}, cache=True) for _ in range(3)),
        (http.get(httpserver.url_for('/c'), params={'foo': '2'}, cache=True) for _ in range(6)),
    ))
    results = await asyncio.gather(*coros)

    assert set(results) == set(
        ['/a?'] * 10
        + ['/b?'] * 5
        + ['/c?foo=1'] * 3
        + ['/c?foo=2'] * 6
    )
    assert set(handler.requests_seen) == {
        '/a?',
        '/b?',
        '/c?foo=1',
        '/c?foo=2',
    }

@pytest.mark.asyncio
async def test_post_request_performs_only_one_identical_request_at_the_same_time(httpserver, mocker, tmp_path):
    mocker.patch.object(http, 'cache_directory', str(tmp_path))

    class Handler(RequestHandler):
        def handle(self, request):
            s = f'{request.full_path} data:{request.data.decode("utf-8")}'
            self.requests_seen.append(s)
            return Response(s)

    handler = Handler()
    for path in ('/a', '/b', '/c', '/d'):
        httpserver.expect_request(
            uri=path,
            method='POST',
        ).respond_with_handler(
            handler,
        )

    coros = tuple(itertools.chain(
        (http.post(httpserver.url_for('/a'), cache=True) for _ in range(10)),
        (http.post(httpserver.url_for('/b'), cache=True) for _ in range(5)),
        (http.post(httpserver.url_for('/c'), data={'foo': '1'}, cache=True) for _ in range(3)),
        (http.post(httpserver.url_for('/c'), data={'foo': '2'}, cache=True) for _ in range(6)),
    ))
    results = await asyncio.gather(*coros)

    assert set(results) == set(
        ["/a? data:"] * 10
        + ['/b? data:'] * 5
        + ['/c? data:foo=1'] * 3
        + ['/c? data:foo=2'] * 6
    )
    assert len(results) == 10 + 5 + 3 + 6
    assert set(handler.requests_seen) == {
        '/a? data:',
        '/b? data:',
        '/c? data:foo=1',
        '/c? data:foo=2',
    }
    assert len(handler.requests_seen) == 4


@pytest.mark.parametrize('cache', (True, False))
@pytest.mark.asyncio
async def test_download_always_disables_caching(cache, mocker, tmp_path):
    mocker.patch('upsies.utils.http.get', AsyncMock(
        return_value=Mock(bytes=b'downloaded data'),
    ))
    filepath = tmp_path / 'downloaded'
    return_value = await http.download('mock url', filepath, cache=cache)
    assert return_value == filepath
    assert http.get.call_args_list == [call('mock url', cache=False)]

@pytest.mark.asyncio
async def test_download_forwards_args_and_kwargs_to_get(mocker, tmp_path):
    mocker.patch('upsies.utils.http.get', AsyncMock(
        return_value=Mock(bytes=b'downloaded data'),
    ))
    filepath = tmp_path / 'downloaded'
    return_value = await http.download('mock url', filepath, 'foo', bar='baz')
    assert return_value == filepath
    assert http.get.call_args_list == [call('mock url', 'foo', bar='baz', cache=False)]

@pytest.mark.asyncio
async def test_download_does_nothing_if_file_exists(mocker, tmp_path):
    mocker.patch('upsies.utils.http.get', AsyncMock(
        return_value=Mock(bytes=b'downloaded data'),
    ))
    filepath = tmp_path / 'downloaded'
    filepath.write_bytes(b'downloaded data')
    return_value = await http.download('mock url', filepath)
    assert return_value == filepath
    assert http.get.call_args_list == []

@pytest.mark.asyncio
async def test_download_writes_filepath(mocker, tmp_path):
    mocker.patch('upsies.utils.http.get', AsyncMock(
        side_effect=errors.RequestError('no response'),
    ))
    filepath = tmp_path / 'downloaded'
    with pytest.raises(errors.RequestError, match=r'^no response$'):
        await http.download('mock url', filepath)
    assert not filepath.exists()

@pytest.mark.asyncio
async def test_download_does_not_write_filepath_if_request_fails(mocker, tmp_path):
    mocker.patch('upsies.utils.http.get', AsyncMock(
        return_value=Mock(bytes=b'downloaded data'),
    ))
    filepath = tmp_path / 'downloaded'
    return_value = await http.download('mock url', filepath)
    assert return_value == filepath
    assert filepath.read_bytes() == b'downloaded data'

@pytest.mark.asyncio
async def test_download_catches_OSError_when_opening_filepath(mocker, tmp_path):
    mocker.patch('upsies.utils.http.get', AsyncMock(
        return_value=Mock(bytes=b'downloaded data'),
    ))
    filepath = tmp_path / 'downloaded'
    mocker.patch('builtins.open', side_effect=OSError('Ouch'))
    with pytest.raises(errors.RequestError, match=rf'^Unable to write {filepath}: Ouch$'):
        await http.download('mock url', filepath)


def test_open_files_opens_files(mocker):
    mocker.patch(
        'upsies.utils.http._get_file_object',
        side_effect=(
            io.BytesIO(b'foo image'),
            io.BytesIO(b'bar text1'),
            io.BytesIO(b'bar text2'),
            io.BytesIO(b'bar text3'),
            io.BytesIO(b'bar text4'),
        ),
    )
    opened_files = http._open_files({
        'a': 'path/to/foo.jpg',
        'b': {'file': 'path/to/bar.txt'},
        'c': {'file': 'path/to/bar.txt', 'filename': 'baz'},
        'd': {'file': 'path/to/bar.txt', 'mimetype': 'text/plain'},
        'e': {'file': 'path/to/bar.txt', 'mimetype': None},
        'f': {'file': io.BytesIO(b'in-memory data1'), 'mimetype': 'weird/type'},
        'g': {'file': io.BytesIO(b'in-memory data2'), 'mimetype': 'weird/type', 'filename': 'kangaroo'},
        'h': {'file': io.BytesIO(b'in-memory data3'), 'mimetype': None, 'filename': 'kangaroo'},
        'i': {'file': io.BytesIO(b'in-memory data4'), 'filename': 'kangaroo'},
    })
    assert tuple(opened_files) == ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i')

    def assert_opened(fieldname, filename, data, mimetype=False):
        assert opened_files[fieldname][0] == filename
        assert opened_files[fieldname][1].read() == data
        if mimetype is False:
            assert len(opened_files[fieldname]) == 2
        else:
            assert opened_files[fieldname][2] == mimetype
            assert len(opened_files[fieldname]) == 3

    assert_opened('a', 'foo.jpg', b'foo image')
    assert_opened('b', 'bar.txt', b'bar text1')
    assert_opened('c', 'baz', b'bar text2')
    assert_opened('d', 'bar.txt', b'bar text3', 'text/plain')
    assert_opened('e', 'bar.txt', b'bar text4', None)
    assert_opened('f', None, b'in-memory data1', 'weird/type')
    assert_opened('g', 'kangaroo', b'in-memory data2', 'weird/type')
    assert_opened('h', 'kangaroo', b'in-memory data3', None)
    assert_opened('i', 'kangaroo', b'in-memory data4')

def test_open_files_catches_invalid_file_value(mocker):
    mocker.patch('upsies.utils.http._get_file_object', return_value='mock file object')
    with pytest.raises(RuntimeError, match=r'^Invalid "file" value in fileinfo: \[1, 2, 3\]$'):
        http._open_files({
            'document': {'file': [1, 2, 3]},
        })

def test_open_files_catches_invalid_fileinfo(mocker):
    mocker.patch('upsies.utils.http._get_file_object', return_value='mock file object')
    with pytest.raises(RuntimeError, match=r'^Invalid fileinfo: \[1, 2, 3\]$'):
        http._open_files({
            'document': [1, 2, 3],
        })

def test_open_files_raises_exception_from_get_file_object(mocker):
    mocker.patch('upsies.utils.http._get_file_object',
                 side_effect=errors.RequestError('bad io'))
    with pytest.raises(errors.RequestError, match=r'^bad io$'):
        http._open_files({
            'image': 'path/to/foo.jpg',
            'document': ('path/to/bar', 'text/plain'),
        })


def test_get_file_object_catches_OSError():
    filepath = 'path/to/foo'
    with pytest.raises(errors.RequestError, match=rf'^{filepath}: No such file or directory$'):
        http._get_file_object(filepath)

def test_get_file_object_returns_fileobj(tmp_path):
    filepath = tmp_path / 'foo'
    filepath.write_bytes(b'hello')
    fileobj = http._get_file_object(filepath)
    assert fileobj.read() == b'hello'


@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_cache_file_without_params(method, mocker):
    def sanitize_filename(filename):
        return filename.replace('a', '#')

    mocker.patch('upsies.utils.fs.sanitize_filename', side_effect=sanitize_filename)
    mocker.patch.object(http, 'cache_directory', '/tmp/foo')
    url = 'http://localhost:123/foo/bar'
    exp_cache_file = f'/tmp/foo/{method.upper()}.http://loc#lhost:123/foo/b#r'
    assert http._cache_file(method, url) == exp_cache_file

@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_cache_file_with_params(method, mocker):
    def sanitize_filename(filename):
        return filename.replace('a', '#')

    mocker.patch('upsies.utils.fs.sanitize_filename', side_effect=sanitize_filename)
    mocker.patch.object(http, 'cache_directory', '/tmp/foo')
    url = 'http://localhost:123'
    params = {'foo': 'a b c', 'bar': 12}
    exp_cache_file = f'/tmp/foo/{method.upper()}.http://loc#lhost:123?foo=#+b+c&b#r=12'
    assert http._cache_file(method, url, params=params) == exp_cache_file

@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_cache_file_with_very_long_params(method, mocker):
    def sanitize_filename(filename):
        return filename.replace('a', '#')

    mocker.patch('upsies.utils.fs.sanitize_filename', side_effect=sanitize_filename)
    mocker.patch.object(http, 'cache_directory', '/tmp/foo')
    url = 'http://localhost:123'
    params = {'foo': 'a b c ' * 100, 'bar': 12}
    exp_cache_file = (
        f'/tmp/foo/{method.upper()}.http://loc#lhost:123?'
        f'[HASH:{sanitize_filename(http._semantic_hash(params))}]'
    )
    assert http._cache_file(method, url, params=params) == exp_cache_file

@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_cache_file_defaults_to_CACHE_DIRPATH(method, mocker):
    def sanitize_filename(filename):
        return filename.replace('a', '#')

    mocker.patch('upsies.utils.fs.sanitize_filename', side_effect=sanitize_filename)
    mocker.patch('upsies.constants.CACHE_DIRPATH', '/tmp/bar')
    url = 'http://localhost:123'
    exp_cache_file = f'/tmp/bar/{method.upper()}.http://loc#lhost:123'
    assert http._cache_file(method, url) == exp_cache_file


def test_from_cache_with_nonexisting_cache_file():
    assert http._from_cache('/no/such/path') is None

def test_from_cache_with_unreadable_cache_file(tmp_path):
    cache_filepath = tmp_path / 'cache_file'
    cache_filepath.write_text('mock data')
    cache_filepath.chmod(0o000)
    try:
        assert http._from_cache(cache_filepath) is None
    finally:
        cache_filepath.chmod(0o600)

@pytest.mark.parametrize(
    argnames='cached_data, max_age, cache_file_age, exp_return_value',
    argvalues=(
        ('föö', 100, 99, http.Result('föö', b'f\xc3\xb6\xc3\xb6')),
        ('föö', 100, 101, None),
    ),
)
def test_from_cache_refuses_to_read_old_cache_file(cached_data, max_age, cache_file_age, exp_return_value, tmp_path):
    cache_filepath = tmp_path / 'cache/file'
    cache_filepath.parent.mkdir(parents=True)
    cache_filepath.write_text(cached_data, encoding='UTF-8')
    mtime = time.time() - cache_file_age
    os.utime(cache_filepath, times=(mtime, mtime))
    cached_result = http._from_cache(cache_filepath, max_age=max_age)
    assert cached_result == exp_return_value


def test_to_cache_cannot_create_cache_directory(mocker):
    mocker.patch('builtins.open')
    mkdir_mock = mocker.patch('upsies.utils.fs.mkdir', side_effect=OSError('No'))
    with pytest.raises(RuntimeError, match=r'^Unable to write cache file mock/path: No$'):
        http._to_cache('mock/path', 'data')
    assert mkdir_mock.call_args_list == [call('mock')]

def test_to_cache_cannot_write_cache_file(mocker):
    open_mock = mocker.patch('builtins.open')
    mkdir_mock = mocker.patch('upsies.utils.fs.mkdir')
    filehandle = open_mock.return_value.__enter__.return_value
    filehandle.write.side_effect = OSError('No')
    with pytest.raises(RuntimeError, match=r'^Unable to write cache file mock/path: No$'):
        http._to_cache('mock/path', 'data')
    assert mkdir_mock.call_args_list == [call('mock')]

def test_to_cache_can_write_cache_file(mocker):
    open_mock = mocker.patch('builtins.open')
    mkdir_mock = mocker.patch('upsies.utils.fs.mkdir')
    filehandle = open_mock.return_value.__enter__.return_value
    assert http._to_cache('mock/path', 'data') is None
    assert open_mock.call_args_list == [call('mock/path', 'wb')]
    assert filehandle.write.call_args_list == [call('data')]
    assert mkdir_mock.call_args_list == [call('mock')]


@pytest.mark.parametrize(
    argnames='obj, exp_bytes',
    argvalues=(
        ('foo',
         b"'foo'"),
        (23,
         b"'23'"),
        (['foo', 'bar', 'baz'],
         b"['bar', 'baz', 'foo']"),
        ({'c': (5, 6, 4), 'a': 1, 'b': [2, 1, 3]},
         b"{'a': '1', 'b': ['1', '2', '3'], 'c': ['4', '5', '6']}"),
    ),
    ids=lambda v: str(v),
)
def test_semantic_hash(obj, exp_bytes):
    assert http._semantic_hash(obj) == hashlib.sha256(exp_bytes).hexdigest()
