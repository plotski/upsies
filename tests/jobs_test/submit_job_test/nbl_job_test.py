import os
import sys
from unittest.mock import Mock, call, patch

import aiohttp
import aiohttp.test_utils
import bs4
import pytest

from upsies import errors
from upsies.jobs.submit import nbl


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


def make_job(tmp_path, **kwargs):
    kw = {
        'homedir': tmp_path / 'foo.project',
        'ignore_cache': False,
        'jobs_before_upload': (),
        'jobs_after_upload': (),
        'tracker_config': {
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://foo',
            'announce': 'http://foo/announce',
            'exclude': 'some files',
        },
    }
    kw.update(kwargs)
    return nbl.SubmitJob(**kw)


def test_trackername():
    assert nbl.SubmitJob.tracker_name == 'NBL'


def _get_response(name):
    filepath = os.path.join(
        os.path.dirname(__file__),
        'cached_responses',
        f'nbl.{name}.html',
    )
    return open(filepath, 'r').read()


@pytest.mark.asyncio
async def test_login_does_nothing_if_already_logged_in(tmp_path):
    job = make_job(tmp_path)
    job._logout_url = 'anything'
    job._auth_key = 'something'
    assert job.logged_in
    http_session_mock = Mock(post=AsyncMock(), get=AsyncMock())
    await job.login(http_session_mock)
    assert job.logged_in
    assert http_session_mock.get.call_args_list == []
    assert http_session_mock.post.call_args_list == []
    assert job._logout_url == 'anything'
    assert job._auth_key == 'something'

@pytest.mark.asyncio
async def test_login_succeeds(tmp_path):
    job = make_job(tmp_path)
    http_session_mock = Mock(post=AsyncMock(), get=AsyncMock())
    http_session_mock.post.return_value.text = AsyncMock(return_value='''
    <html>
      <input name="auth" value="12345" />
      <a href="logout.php?asdfasdf">logout</a>
    </html>
    ''')
    await job.login(http_session_mock)
    assert http_session_mock.get.call_args_list == []
    assert http_session_mock.post.call_args_list == [call(
        url='http://foo' + job._url_path['login'],
        data={
            'username': 'bunny',
            'password': 'hunter2',
            'twofa': '',
            'login': 'Login',
        }
    )]
    assert job.logged_in
    assert job._logout_url == 'http://foo/logout.php?asdfasdf'
    assert job._auth_key == '12345'

@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='Python < 3.8 refuses to patch in async tests')
@pytest.mark.asyncio
@pytest.mark.parametrize(
    argnames='method_name',
    argvalues=(
        'parse_html',
        '_report_login_error',
        '_store_auth_key',
        '_store_logout_url',
    ),
)
@patch('upsies.jobs.submit.nbl.SubmitJob.dump_html')
async def test_login_dumps_html_if_handling_response_fails(dump_html_mock, method_name, tmp_path):
    http_session_mock = Mock(post=AsyncMock(), get=AsyncMock())
    http_session_mock.post.return_value.text = AsyncMock(return_value='''
    <html>
      <input name="auth" value="12345" />
      <a href="logout.php?asdfasdf">logout</a>
    </html>
    ''')
    job = make_job(tmp_path)
    with patch.object(job, method_name) as method_mock:
        method_mock.side_effect = Exception('Oooph!')
        with pytest.raises(Exception, match=r'^Oooph\!$'):
            await job.login(http_session_mock)
    assert not job.logged_in
    assert http_session_mock.get.call_args_list == []
    assert http_session_mock.post.call_args_list == [call(
        url='http://foo' + job._url_path['login'],
        data={
            'username': 'bunny',
            'password': 'hunter2',
            'twofa': '',
            'login': 'Login',
        }
    )]
    assert not job.logged_in
    assert dump_html_mock.call_args_list == [
        call('login.html', http_session_mock.post.return_value.text.return_value),
    ]

@pytest.mark.parametrize(
    argnames='error, exp_message',
    argvalues=(
        pytest.param(
            'login.auth-failed',
            r'Your username or password was incorrect\.',
            id='login.auth-failed',
        ),
        pytest.param(
            'login.banned',
            (r'Your account has been disabled\. This is either due '
             r'to inactivity or rule violation\.'),
            id='login.banned',
        ),
    ),
)
def test_report_login_error(error, exp_message, tmp_path):
    job = make_job(tmp_path)
    html = bs4.BeautifulSoup(
        markup=_get_response(error),
        features='html.parser',
    )
    with pytest.raises(errors.RequestError, match=rf'^Login failed: {exp_message}$'):
        job._report_login_error(html)


def test_logged_in(tmp_path):
    job = make_job(tmp_path)
    # job.logged_in must be True if "_logout_url" and "_auth_key" are set
    assert job.logged_in is False
    job._logout_url = 'asdf'
    assert job.logged_in is False
    job._auth_key = 'asdf'
    assert job.logged_in is True
    delattr(job, '_logout_url')
    assert job.logged_in is False
    job._logout_url = 'asdf'
    assert job.logged_in is True
    delattr(job, '_auth_key')
    assert job.logged_in is False

@pytest.mark.asyncio
@pytest.mark.parametrize(
    argnames=('logout_url', 'auth_key'),
    argvalues=(
        ('http://localhost/logout.php', '12345'),
        ('http://localhost/logout.php', None),
        (None, '12345'),
        (None, None),
    ),
)
async def test_logout(logout_url, auth_key, tmp_path):
    job = make_job(tmp_path)
    if logout_url is not None:
        job._logout_url = logout_url
    if auth_key is not None:
        job._auth_key = auth_key
    http_session_mock = Mock(post=AsyncMock(), get=AsyncMock())
    await job.logout(http_session_mock)
    if logout_url is not None:
        assert http_session_mock.get.call_args_list == [call(logout_url)]
    assert http_session_mock.post.call_args_list == []
    assert not hasattr(job, '_logout_url')
    assert not hasattr(job, '_auth_key')


@pytest.mark.asyncio
async def test_upload_without_being_logged_in(tmp_path):
    job = make_job(tmp_path)
    http_session_mock = Mock(post=AsyncMock(), get=AsyncMock())
    with pytest.raises(RuntimeError, match=r'^upload\(\) called before login\(\)$'):
        await job.upload(http_session_mock)
    assert http_session_mock.get.call_args_list == []
    assert http_session_mock.post.call_args_list == []


class MockServer(aiohttp.test_utils.TestServer):
    def __init__(self, responses):
        super().__init__(aiohttp.web.Application())
        self.requests_seen = []
        self._csrf_token = 'random CSRF token'

        def make_responder(response):
            async def responder(request):
                request_seen = {
                    'method': request.method,
                    'user-agent': request.headers.get('User-Agent', ''),
                }

                async def read_multipart(request):
                    multipart = {}
                    reader = await request.multipart()
                    while True:
                        part = await reader.next()
                        if part is None:
                            return multipart
                        else:
                            multipart[part.name] = await part.read()

                if request.content_type == 'multipart/form-data':
                    request_seen[request.content_type] = await read_multipart(request)
                else:
                    request_seen[request.content_type] = await request.text()

                self.requests_seen.append(request_seen)

                if isinstance(response, Exception):
                    raise response
                else:
                    return response
            return responder

        for methods, path, response in responses:
            for method in methods:
                self.app.router.add_route(method, path, make_responder(response))
        self.responses = list(responses)

    def url(self, path):
        return f'http://localhost:{self.port}{path}'


@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='Python < 3.8 refuses to patch in async tests')
@pytest.mark.asyncio
@patch('upsies.jobs.submit.nbl.SubmitJob._translate_category', Mock(return_value=b'mock category'))
async def test_upload_succeeds(tmp_path):
    responses = (
        (('post',), '/upload.php', aiohttp.web.HTTPTemporaryRedirect('/torrents.php?id=123')),
    )
    torrent_file = tmp_path / 'foo.torrent'
    torrent_file.write_bytes(b'mocked torrent metainfo')
    async with MockServer(responses) as srv:
        job = make_job(
            tmp_path,
            tracker_config={
                'username': 'bunny',
                'password': 'hunter2',
                'base_url': srv.url(''),
                'announce': 'http://foo/announce',
                'exclude': 'some files',
            },
        )
        job._logout_url = 'logout.php'
        job._auth_key = 'mocked auth key'
        job._metadata = {
            'create-torrent': (str(torrent_file),),
            'mediainfo': ('mocked mediainfo',),
            'tvmaze-id': ('12345',),
            'category': ('mock category',),
        }
        async with aiohttp.ClientSession(headers={'User-Agent': 'test client'}) as client:
            torrent_page_url = await job.upload(client)
        assert torrent_page_url == srv.url('/torrents.php?id=123')
        assert srv.requests_seen == [{
            'method': 'POST',
            'user-agent': 'test client',
            'multipart/form-data': {
                'MAX_FILE_SIZE': bytearray(b'1048576'),
                'auth': bytearray(b'mocked auth key'),
                'category': bytearray(b'mock category'),
                'desc': bytearray(b'mocked mediainfo'),
                'file_input': bytearray(b'mocked torrent metainfo'),
                'fontfont': bytearray(b'-1'),
                'fontsize': bytearray(b'-1'),
                'genre_tags': bytearray(b''),
                'image': bytearray(b''),
                'media': bytearray(b'mocked mediainfo'),
                'mediaclean': bytearray(b'[mediainfo]mocked mediainfo[/mediainfo]'),
                'submit': bytearray(b'true'),
                'tags': bytearray(b''),
                'title': bytearray(b''),
                'tvmazeid': bytearray(b'12345'),
            },
        }]

@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='Python < 3.8 refuses to patch in async tests')
@pytest.mark.asyncio
@patch('upsies.jobs.submit.nbl.SubmitJob._translate_category', Mock(return_value=b'mock category'))
@patch('upsies.jobs.submit.nbl.SubmitJob.dump_html')
async def test_upload_finds_error_message(dump_html_mock, tmp_path):
    responses = (
        (('post',), '/upload.php', aiohttp.web.Response(text='''
        <html>
          <div id="messagebar">Something went wrong</div>
        </html>
        ''')),
    )
    torrent_file = tmp_path / 'foo.torrent'
    torrent_file.write_bytes(b'mocked torrent metainfo')
    async with MockServer(responses) as srv:
        job = make_job(
            tmp_path,
            tracker_config={
                'username': 'bunny',
                'password': 'hunter2',
                'base_url': srv.url(''),
                'announce': 'http://foo/announce',
                'exclude': 'some files',
            },
        )
        job._logout_url = 'logout.php'
        job._auth_key = 'mocked auth key'
        job._metadata = {
            'create-torrent': (str(torrent_file),),
            'mediainfo': ('mocked mediainfo',),
            'tvmaze-id': ('12345',),
            'category': ('mock category',),
        }
        with pytest.raises(errors.RequestError, match=r'^Upload failed: Something went wrong$'):
            async with aiohttp.ClientSession() as client:
                await job.upload(client)
    assert dump_html_mock.call_args_list == []

@pytest.mark.skipif(sys.version_info < (3, 8),
                    reason='Python < 3.8 refuses to patch in async tests')
@pytest.mark.asyncio
@patch('upsies.jobs.submit.nbl.SubmitJob._translate_category', Mock(return_value=b'mock category'))
@patch('upsies.jobs.submit.nbl.SubmitJob.dump_html')
async def test_upload_fails_to_find_error_message(dump_html_mock, tmp_path):
    responses = (
        (('post',), '/upload.php', aiohttp.web.Response(text='mocked html')),
    )
    torrent_file = tmp_path / 'foo.torrent'
    torrent_file.write_bytes(b'mocked torrent metainfo')
    async with MockServer(responses) as srv:
        job = make_job(
            tmp_path,
            tracker_config={
                'username': 'bunny',
                'password': 'hunter2',
                'base_url': srv.url(''),
                'announce': 'http://foo/announce',
                'exclude': 'some files',
            },
        )
        job._logout_url = 'logout.php'
        job._auth_key = 'mocked auth key'
        job._metadata = {
            'create-torrent': (str(torrent_file),),
            'mediainfo': ('mocked mediainfo',),
            'tvmaze-id': ('12345',),
            'category': ('mock category',),
        }
        with pytest.raises(RuntimeError, match=r'^Failed to find error message$'):
            async with aiohttp.ClientSession() as client:
                await job.upload(client)
    assert dump_html_mock.call_args_list == [
        call('upload.html', 'mocked html'),
    ]

@pytest.mark.parametrize(
    argnames=('category', 'exp_category'),
    argvalues=(
        ('episode', '1'),
        ('Episode', '1'),
        ('EPISODE', '1'),
        ('season', '3'),
        ('Season', '3'),
        ('SEASON', '3'),
    ),
)
def test_valid_request_category(category, exp_category, tmp_path):
    job = make_job(tmp_path)
    assert job._translate_category(category) == exp_category

def test_invalid_request_category(tmp_path):
    job = make_job(tmp_path)
    with pytest.raises(errors.RequestError, match=r'^Unsupported type: movie$'):
        job._translate_category('movie')
