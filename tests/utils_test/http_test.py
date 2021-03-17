import asyncio
import base64
import io
import itertools
import re
from unittest.mock import Mock, call

import httpx
import pytest
from pytest_httpserver.httpserver import Response

from upsies import __project_name__, __version__, errors
from upsies.utils import http


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
    argnames=('auth', 'cache', 'user_agent', 'allow_redirects'),
    argvalues=(
        (None, False, False, True),
        (('foo', 'bar'), False, True, False),
        (('bar', 'foo'), True, False, True),
        (None, True, True, False),
    ),
)
@pytest.mark.asyncio
async def test_get_forwards_arguments_to_request(auth, cache, user_agent, allow_redirects, mocker):
    request_mock = mocker.patch('upsies.utils.http._request', new_callable=AsyncMock)
    result = await http.get(
        url='http://localhost:123/foo',
        headers={'foo': 'bar'},
        params={'bar': 'baz'},
        auth=auth,
        cache=cache,
        user_agent=user_agent,
        allow_redirects=allow_redirects,
    )
    assert request_mock.call_args_list == [
        call(
            method='GET',
            url='http://localhost:123/foo',
            headers={'foo': 'bar'},
            params={'bar': 'baz'},
            auth=auth,
            cache=cache,
            user_agent=user_agent,
            allow_redirects=allow_redirects,
        )
    ]
    assert result is request_mock.return_value

@pytest.mark.parametrize(
    argnames=('auth', 'cache', 'user_agent', 'allow_redirects'),
    argvalues=(
        (('a', 'b'), False, False, False),
        (None, False, True, False),
        (('b', 'a'), True, False, True),
        (None, True, True, True),
    ),
)
@pytest.mark.asyncio
async def test_post_forwards_arguments_to_request(auth, cache, user_agent, allow_redirects, mocker):
    request_mock = mocker.patch('upsies.utils.http._request', new_callable=AsyncMock)
    result = await http.post(
        url='http://localhost:123/foo',
        headers={'foo': 'bar'},
        data=b'foo',
        files=b'bar',
        auth=auth,
        cache=cache,
        user_agent=user_agent,
        allow_redirects=allow_redirects,
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
            user_agent=user_agent,
            allow_redirects=allow_redirects,
        )
    ]
    assert result is request_mock.return_value


def test_Result_is_string():
    r = http.Result('foo', b'foo')
    assert isinstance(r, str)
    assert r == 'foo'

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

def test_Result_bytes():
    r = http.Result('föö', bytes('föö', 'utf-8'))
    assert r.bytes == bytes('föö', 'utf-8')
    assert str(r.bytes, 'utf-8') == 'föö'

def test_Result_json():
    r = http.Result('{"this":"that"}', b'{"this":"that"}')
    assert r.json() == {'this': 'that'}
    r = http.Result('{"this":"that"', b'{"this":"that"')
    assert r == '{"this":"that"'
    with pytest.raises(errors.RequestError, match=r'^Malformed JSON: {"this":"that": '):
        r.json()

def test_Result_repr():
    r = http.Result('föö', bytes('föö', 'utf-8'))
    assert repr(r) == f"Result(text='föö', bytes={bytes('föö', 'utf-8')!r}, headers={{}}, status_code=None)"


@pytest.mark.asyncio
async def test_request_with_invalid_url(mock_cache):
    url = r'http://:/foo:bar'
    with pytest.raises(errors.RequestError, match=rf'^{re.escape(url)}: Missing hostname in URL\.$') as excinfo:
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
            call.from_cache(mock_cache.cache_file.return_value),
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
    print(httpserver)
    print(dir(httpserver))
    result = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        cache=True,
    )
    assert result == 'have this'
    assert isinstance(result, http.Result)
    assert mock_cache.mock_calls == [
        call.cache_file(method, httpserver.url_for('/foo'), {}),
        call.from_cache(mock_cache.cache_file.return_value),
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

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_sends_data(method, mock_cache, httpserver):
    data = b'bleepbloop'
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

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_sends_user_agent(method, mock_cache, httpserver):
    class Handler(RequestHandler):
        def handle(self, request):
            assert request.headers.get('User-Agent') == f'{__project_name__}/{__version__}'
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
async def test_request_does_not_send_user_agent(method, mock_cache, httpserver):
    class Handler(RequestHandler):
        def handle(self, request):
            assert request.headers.get('User-Agent') is None
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
        user_agent=False,
    )
    assert result == 'have this'
    assert isinstance(result, http.Result)


@pytest.mark.parametrize('allow_redirects', (True, False))
@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.parametrize('status_code', ('301', '302', '303'))
@pytest.mark.asyncio
async def test_request_with_allow_redirects(status_code, method, allow_redirects, mock_cache, httpserver):
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
        method='GET',
    ).respond_with_handler(
        handler,
    )

    result = await http._request(
        method=method,
        url=httpserver.url_for('/foo'),
        allow_redirects=allow_redirects,
    )
    if allow_redirects:
        assert result == 'redirected'
    else:
        assert result == 'not redirected'
    assert isinstance(result, http.Result)


@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_catches_HTTP_error_status(method, mock_cache, httpserver):
    url = httpserver.url_for('/foo')
    httpserver.expect_request(
        uri='/foo',
        method=method,
    ).respond_with_data(
        'Dave is not here',
        status=404,
        headers={'foo': 'bar'},
    )
    with pytest.raises(errors.RequestError, match=rf'^{url}: Dave is not here$') as excinfo:
        await http._request(method=method, url=url)
    assert excinfo.value.status_code == 404
    assert excinfo.value.headers['foo'] == 'bar'

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_catches_NetworkError(method, mock_cache):
    url = 'http://127.0.0.1:12345/foo/bar/baz'
    with pytest.raises(errors.RequestError, match=rf'^{url}: .*Connect call failed') as excinfo:
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
    mocker.patch.object(http._client, 'send', Mock(side_effect=exc))
    url = 'http://localhost:12345/foo/bar/baz'
    with pytest.raises(errors.RequestError, match=rf'^{url}: Timeout$') as excinfo:
        await http._request(method=method, url=url)
    assert excinfo.value.status_code is None
    assert excinfo.value.headers == {}

@pytest.mark.parametrize('method', ('GET', 'POST'))
@pytest.mark.asyncio
async def test_request_catches_HTTPError(method, mock_cache, mocker):
    exc = httpx.HTTPError(
        message='Some error',
        request='mock request',
    )
    mocker.patch.object(http._client, 'send', Mock(side_effect=exc))
    url = 'http://localhost:12345/foo/bar/baz'
    with pytest.raises(errors.RequestError, match=rf'^{url}: Some error$') as excinfo:
        await http._request(method=method, url=url)
    assert excinfo.value.status_code is None
    assert excinfo.value.headers == {}


@pytest.mark.asyncio
async def test_get_performs_only_one_identical_request_at_the_same_time(httpserver, mocker, tmp_path):
    mocker.patch('upsies.utils.fs.tmpdir', return_value=str(tmp_path))

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
    mocker.patch('upsies.utils.fs.tmpdir', return_value=str(tmp_path))

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


def test_open_files_raises_exception_from_get_fileobj(mocker):
    mocker.patch('upsies.utils.http._get_fileobj',
                 side_effect=errors.RequestError('bad io'))
    with pytest.raises(errors.RequestError, match=r'^bad io$'):
        http._open_files({
            'image': 'path/to/foo.jpg',
            'document': ('path/to/bar', 'text/plain'),
        })

def test_open_files_opens_files(mocker):
    mocker.patch(
        'upsies.utils.http._get_fileobj',
        side_effect=(
            io.BytesIO(b'hello world'),
            io.BytesIO(b'goodbye world'),
        ),
    )
    opened_files = http._open_files({
        'image': 'path/to/foo.jpg',
        'document': ('path/to/bar', 'text/plain'),
    })
    assert tuple(opened_files) == ('image', 'document')
    assert opened_files['image'][0] == 'foo.jpg'
    assert opened_files['image'][1].read() == b'hello world'
    assert len(opened_files['image']) == 2
    assert opened_files['document'][0] == 'bar'
    assert opened_files['document'][1].read() == b'goodbye world'
    assert opened_files['document'][2] == 'text/plain'
    assert len(opened_files['document']) == 3


def test_get_fileobj_catches_OSError():
    filepath = 'path/to/foo'
    with pytest.raises(errors.RequestError, match=rf'^{filepath}: No such file or directory$'):
        http._get_fileobj(filepath)

def test_get_fileobj_returns_fileobj(tmp_path):
    filepath = tmp_path / 'foo'
    filepath.write_bytes(b'hello')
    fileobj = http._get_fileobj(filepath)
    assert fileobj.read() == b'hello'


@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_cache_file_without_params(method, mocker):
    mocker.patch('upsies.utils.fs.tmpdir', return_value='/tmp/foo')
    url = 'http://localhost:123/foo/bar'
    exp_cache_file = f'/tmp/foo/{method.upper()}.http:__localhost:123_foo_bar'
    assert http._cache_file(method, url) == exp_cache_file

@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_cache_file_with_params(method, mocker):
    mocker.patch('upsies.utils.fs.tmpdir', return_value='/tmp/foo')
    url = 'http://localhost:123'
    params = {'foo': 'a b c', 'bar': 12}
    exp_cache_file = f'/tmp/foo/{method.upper()}.http:__localhost:123?foo=a+b+c&bar=12'
    assert http._cache_file(method, url, params=params) == exp_cache_file

@pytest.mark.parametrize('method', ('GET', 'POST'))
def test_cache_file_with_very_long_params(method, mocker):
    mocker.patch('upsies.utils.fs.tmpdir', return_value='/tmp/foo')
    url = 'http://localhost:123'
    params = {'foo': 'a b c ' * 100, 'bar': 12}
    exp_cache_file = (
        f'/tmp/foo/{method.upper()}.http:__localhost:123?'
        f'[HASH:{http._semantic_hash(params)}]'
    )
    assert http._cache_file(method, url, params=params) == exp_cache_file


def test_from_cache_cannot_read_cache_file(mocker):
    open_mock = mocker.patch('builtins.open', side_effect=OSError('Ouch'))
    assert http._from_cache('mock/path') is None
    assert open_mock.call_args_list == [call('mock/path', 'rb'), call('mock/path', 'rb')]

def test_from_cache_can_read_cache_file(mocker):
    open_mock = mocker.patch('builtins.open')
    filehandle = open_mock.return_value.__enter__.return_value
    filehandle.read.return_value = b'cached data'
    assert http._from_cache('mock/path') == http.Result('cached data', b'cached data')
    assert open_mock.call_args_list == [call('mock/path', 'rb'), call('mock/path', 'rb')]
    assert filehandle.read.call_args_list == [call(), call()]


def test_to_cache_cannot_write_cache_file(mocker):
    open_mock = mocker.patch('builtins.open')
    filehandle = open_mock.return_value.__enter__.return_value
    filehandle.write.side_effect = OSError('No')
    with pytest.raises(RuntimeError, match=r'^Unable to write cache file mock/path: No$'):
        http._to_cache('mock/path', 'data')

def test_to_cache_can_write_cache_file(mocker):
    open_mock = mocker.patch('builtins.open')
    filehandle = open_mock.return_value.__enter__.return_value
    assert http._to_cache('mock/path', 'data') is None
    assert open_mock.call_args_list == [call('mock/path', 'wb')]
    assert filehandle.write.call_args_list == [call('data')]
