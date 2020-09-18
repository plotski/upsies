import sys
from unittest.mock import Mock, call, patch

import aiohttp
import aiohttp.test_utils
import pytest

from upsies import errors
from upsies.jobs.submit import nbl

needs_python38 = pytest.mark.skipif(
    sys.version_info < (3, 8),
    reason='Python < 3.8 refuses to mock',
)


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
        'content_path': tmp_path / 'foo',
        'args': Mock(),
        'config': {
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://foo',
            'announce': 'http://foo/announce',
            'exclude': 'some files',
        },
    }
    kw.update(kwargs)
    return nbl.SubmissionJob(**kw)


def test_trackername():
    assert nbl.SubmissionJob.trackername == 'NBL'


@patch('upsies.utils.fs.projectdir')
@patch('upsies.jobs.torrent.CreateTorrentJob')
def test_torrent_job(CreateTorrentJob_mock, projectdir_mock, tmp_path):
    job = make_job(tmp_path)
    assert job._torrent_job is CreateTorrentJob_mock.return_value
    assert CreateTorrentJob_mock.call_args_list == [call(
        homedir=projectdir_mock.return_value,
        ignore_cache=False,
        content_path=tmp_path / 'foo',
        exclude_regexs='some files',
        trackername=job.trackername,
        announce_url='http://foo/announce',
        source='NBL',
    )]
    assert projectdir_mock.call_args_list == [call(tmp_path / 'foo')]

@patch('upsies.utils.fs.projectdir')
@patch('upsies.jobs.search.SearchDbJob')
def test_search_job(SearchDbJob_mock, projectdir_mock, tmp_path):
    job = make_job(tmp_path)
    assert job._search_job is SearchDbJob_mock.return_value
    assert SearchDbJob_mock.call_args_list == [call(
        homedir=projectdir_mock.return_value,
        ignore_cache=False,
        content_path=tmp_path / 'foo',
        db='tvmaze',
    )]
    assert projectdir_mock.call_args_list == [call(tmp_path / 'foo')]

@patch('upsies.utils.fs.projectdir', Mock())
@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
def test_jobs(CreateTorrentJob_mock, SearchDbJob_mock, tmp_path):
    job = make_job(tmp_path)
    assert len(job.jobs) == 3
    assert job.jobs[0] is CreateTorrentJob_mock.return_value
    assert job.jobs[1] is SearchDbJob_mock.return_value
    assert job.jobs[2] is job


@patch('upsies.utils.fs.projectdir', Mock())
@patch('upsies.jobs.torrent.CreateTorrentJob')
def test_torrent_filepath(CreateTorrentJob_mock, tmp_path):
    job = make_job(tmp_path)
    CreateTorrentJob_mock.return_value.output = ()
    assert job.torrent_filepath is None
    CreateTorrentJob_mock.return_value.output = ('path/to/torrent',)
    assert job.torrent_filepath == 'path/to/torrent'


@patch('upsies.utils.fs.projectdir', Mock())
@patch('upsies.jobs.search.SearchDbJob')
def test_tvmaze_id(SearchDbJob_mock, tmp_path):
    job = make_job(tmp_path)
    SearchDbJob_mock.return_value.output = ()
    assert job.tvmaze_id is None
    SearchDbJob_mock.return_value.output = ('1234',)
    assert job.tvmaze_id == '1234'


@patch('upsies.jobs.submit.nbl.mediainfo')
@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
def test_mediainfo(CreateTorrentJob_mock, SearchDbJob_mock, mediainfo_mock, tmp_path):
    job = make_job(tmp_path)
    mediainfo_mock.as_string.return_value = '<mediainfo>'
    assert job.mediainfo == '<mediainfo>'
    assert mediainfo_mock.as_string.call_args_list == [call(job.content_path)]


@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
@pytest.mark.asyncio
async def test_login_does_nothing_if_already_logged_in(CreateTorrentJob_mock, SearchDbJob_mock, tmp_path):
    job = make_job(tmp_path)
    job._logout_url = 'anything'
    job._auth_key = 'something'
    assert job.logged_in
    client_session_mock = Mock(post=AsyncMock(), get=AsyncMock())
    await job.login(client_session_mock)
    assert job.logged_in
    assert client_session_mock.get.call_args_list == []
    assert client_session_mock.post.call_args_list == []
    assert job._logout_url == 'anything'
    assert job._auth_key == 'something'

@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
@pytest.mark.asyncio
async def test_login_succeeds(CreateTorrentJob_mock, SearchDbJob_mock, tmp_path):
    job = make_job(tmp_path)
    client_session_mock = Mock(post=AsyncMock(), get=AsyncMock())
    client_session_mock.post.return_value.text = AsyncMock(return_value='''
    <html>
      <input name="auth" value="12345" />
      <a href="logout.php?asdfasdf">logout</a>
    </html>
    ''')
    await job.login(client_session_mock)
    assert client_session_mock.get.call_args_list == []
    assert client_session_mock.post.call_args_list == [call(
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


@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
def test_report_login_error_reports_error(CreateTorrentJob_mock, SearchDbJob_mock, tmp_path):
    job = make_job(tmp_path)
    html = Mock()
    html.find.return_value.find.return_value.string.strip.return_value = 'An error message'
    with pytest.raises(errors.RequestError, match=r'^Login failed: An error message$'):
        job._report_login_error(html)
    assert html.find.call_args_list == [call(id='loginform')]
    assert html.find.return_value.find.call_args_list == [call(class_='warning')]

@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
def test_report_login_error_does_not_find_error(CreateTorrentJob_mock, SearchDbJob_mock, tmp_path):
    job = make_job(tmp_path)
    html = Mock()
    html.find.return_value.find.return_value.string.strip.return_value = ''
    assert job._report_login_error(html) is None
    html.find.return_value.find.return_value = None
    assert job._report_login_error(html) is None
    html.find.return_value = None
    assert job._report_login_error(html) is None


@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
def test_logged_in(CreateTorrentJob_mock, SearchDbJob_mock, tmp_path):
    job = make_job(tmp_path)
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


@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
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
async def test_logout(CreateTorrentJob_mock, SearchDbJob_mock, logout_url, auth_key, tmp_path):
    job = make_job(tmp_path)
    if logout_url is not None:
        job._logout_url = logout_url
    if auth_key is not None:
        job._auth_key = auth_key
    client_session_mock = Mock(post=AsyncMock(), get=AsyncMock())
    await job.logout(client_session_mock)
    if logout_url is not None:
        assert client_session_mock.get.call_args_list == [call(logout_url)]
    assert client_session_mock.post.call_args_list == []
    assert not hasattr(job, '_logout_url')
    assert not hasattr(job, '_auth_key')


@patch('upsies.utils.fs.projectdir', Mock())
@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
@pytest.mark.asyncio
async def test_upload_without_being_logged_in(CreateTorrentJob_mock, SearchDbJob_mock, tmp_path):
    job = make_job(tmp_path)
    client_session_mock = Mock(post=AsyncMock(), get=AsyncMock())
    with pytest.raises(RuntimeError, match=r'^upload\(\) called before login\(\)$'):
        await job.upload(client_session_mock)
    assert client_session_mock.get.call_args_list == []
    assert client_session_mock.post.call_args_list == []

@patch('upsies.utils.fs.projectdir', Mock())
@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
@pytest.mark.asyncio
async def test_upload_without_torrent_filepath(CreateTorrentJob_mock, SearchDbJob_mock, tmp_path):
    job = make_job(tmp_path)
    job._logout_url = 'logout.php'
    job._auth_key = 'asdf'
    CreateTorrentJob_mock.return_value.output = ()
    client_session_mock = Mock(post=AsyncMock(), get=AsyncMock())
    with pytest.raises(RuntimeError, match=r'^upload\(\) called before torrent file creation finished$'):
        await job.upload(client_session_mock)
    assert client_session_mock.get.call_args_list == []
    assert client_session_mock.post.call_args_list == []

@needs_python38
@patch('upsies.utils.fs.projectdir', Mock())
@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
@pytest.mark.asyncio
async def test_upload_without_tvmaze_id(CreateTorrentJob_mock, SearchDbJob_mock, tmp_path):
    job = make_job(tmp_path)
    job._logout_url = 'logout.php'
    job._auth_key = 'asdf'
    CreateTorrentJob_mock.return_value.output = ('path/to/torrent',)
    SearchDbJob_mock.return_value.output = ()
    client_session_mock = Mock(post=AsyncMock(), get=AsyncMock())
    with pytest.raises(RuntimeError, match=r'^upload\(\) called before TVmaze ID was picked$'):
        await job.upload(client_session_mock)
    assert client_session_mock.post.call_args_list == []
    assert client_session_mock.get.call_args_list == []


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


@needs_python38
@patch('upsies.utils.fs.projectdir', Mock())
@patch('upsies.jobs.submit.nbl.mediainfo')
@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
@pytest.mark.asyncio
async def test_upload_succeeds(CreateTorrentJob_mock, SearchDbJob_mock, mediainfo_mock, tmp_path):
    tvmaze_id = '12345'
    torrent_file = tmp_path / 'foo.torrent'
    torrent_file.write_bytes(b'mocked torrent metainfo')

    responses = (
        (('post',), '/upload.php', aiohttp.web.HTTPTemporaryRedirect('/torrents.php?id=123')),
    )
    async with MockServer(responses) as srv:
        job = make_job(
            tmp_path,
            config={
                'username': 'bunny',
                'password': 'hunter2',
                'base_url': srv.url(''),
                'announce': 'http://foo/announce',
                'exclude': 'some files',
            },
        )
        job._logout_url = 'logout.php'
        job._auth_key = 'mocked auth key'
        CreateTorrentJob_mock.return_value.output = (torrent_file,)
        SearchDbJob_mock.return_value.output = (tvmaze_id,)
        mediainfo_mock.as_string.return_value = 'mocked mediainfo'

        async with aiohttp.ClientSession(headers={'User-Agent': 'test client'}) as client:
            torrent_page_url = await job.upload(client)

        assert torrent_page_url == srv.url('/torrents.php?id=123')
        assert srv.requests_seen == [{
            'method': 'POST',
            'user-agent': 'test client',
            'multipart/form-data': {
                'MAX_FILE_SIZE': bytearray(b'1048576'),
                'auth': bytearray(b'mocked auth key'),
                'category': bytearray(b'3'),
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

@needs_python38
@patch('upsies.utils.fs.projectdir', Mock())
@patch('upsies.jobs.submit.nbl.mediainfo')
@patch('upsies.jobs.search.SearchDbJob')
@patch('upsies.jobs.torrent.CreateTorrentJob')
@pytest.mark.asyncio
async def test_upload_fails(CreateTorrentJob_mock, SearchDbJob_mock, mediainfo_mock, tmp_path):
    tvmaze_id = '12345'
    torrent_file = tmp_path / 'foo.torrent'
    torrent_file.write_bytes(b'mocked torrent metainfo')
    responses = (
        (('post',), '/upload.php', aiohttp.web.Response(text='''
        <html>
          <div id="messagebar">Something went wrong</div>
        </html>
        ''')),
    )
    async with MockServer(responses) as srv:
        job = make_job(
            tmp_path,
            config={
                'username': 'bunny',
                'password': 'hunter2',
                'base_url': srv.url(''),
                'announce': 'http://foo/announce',
                'exclude': 'some files',
            },
        )
        job._logout_url = 'logout.php'
        job._auth_key = 'mocked auth key'
        CreateTorrentJob_mock.return_value.output = (torrent_file,)
        SearchDbJob_mock.return_value.output = (tvmaze_id,)
        mediainfo_mock.as_string.return_value = 'mocked mediainfo'

        with pytest.raises(errors.RequestError, match=r'^Upload failed: Something went wrong$'):
            async with aiohttp.ClientSession() as client:
                await job.upload(client)
