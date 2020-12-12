import os
from unittest.mock import Mock, call, patch

import bs4
import pytest
from pytest_httpserver.httpserver import Response

from upsies import __project_name__, __version__, errors
from upsies.trackers import nbl
from upsies.utils import ReleaseType


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


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


def make_tracker(tmp_path, **kwargs):
    kw = {
        'config': {
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://nbl.local',
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
        'homedir': tmp_path / 'foo.project',
        'ignore_cache': False,
        'content_path': '/path/to/foo',
        'tracker_name': 'ASDF',
        'btclient': Mock(),
        'torrent_destination': None,

    }
    kw.update(kwargs)
    return nbl.Tracker(**kw)


def test_trackername():
    assert nbl.Tracker.name == 'NBL'


def test_jobs_before_upload(tmp_path, mocker):
    create_torrent_job_mock = mocker.patch('upsies.trackers.nbl.Tracker.create_torrent_job', Mock())
    mediainfo_job_mock = mocker.patch('upsies.trackers.nbl.Tracker.mediainfo_job', Mock())
    tvmaze_job_mock = mocker.patch('upsies.trackers.nbl.Tracker.tvmaze_job', Mock())
    category_job_mock = mocker.patch('upsies.trackers.nbl.Tracker.category_job', Mock())
    tracker = make_tracker(tmp_path)
    assert tuple(tracker.jobs_before_upload) == (
        create_torrent_job_mock,
        mediainfo_job_mock,
        tvmaze_job_mock,
        category_job_mock,
    )


@pytest.mark.parametrize(
    argnames=('guessit_guess', 'focused_choice'),
    argvalues=(
        (ReleaseType.episode, 'Episode'),
        (ReleaseType.season, 'Season'),
        (ReleaseType.movie, 'Season'),
        (ReleaseType.unknown, 'Season'),
        ('episode', 'Episode'),
        ('season', 'Season'),
        ('movie', 'Season'),
        ('', 'Season'),
        (None, 'Season'),
    ),
)
def test_category_job(guessit_guess, focused_choice, tmp_path, mocker):
    mocker.patch('upsies.utils.guessit.guessit', return_value={'type': guessit_guess})
    ChoiceJob_mock = mocker.patch('upsies.jobs.prompt.ChoiceJob', Mock())
    tracker = make_tracker(tmp_path)
    assert tracker.category_job == ChoiceJob_mock.return_value
    assert ChoiceJob_mock.call_args_list == [
        call(
            name='category',
            label='Category',
            homedir=tracker.info.homedir,
            ignore_cache=tracker.info.ignore_cache,
            choices=('Season', 'Episode'),
            focused=focused_choice,
        ),
    ]


@pytest.mark.asyncio
async def test_login_does_nothing_if_already_logged_in(tmp_path, mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    tracker = make_tracker(tmp_path)
    tracker._logout_url = 'anything'
    tracker._auth_key = 'something'
    assert tracker.logged_in
    await tracker.login()
    assert tracker.logged_in
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == []
    assert tracker._logout_url == 'anything'
    assert tracker._auth_key == 'something'

@pytest.mark.asyncio
async def test_login_succeeds(tmp_path, mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(
        return_value='''
            <html>
                <input name="auth" value="12345" />
                <a href="logout.php?asdfasdf">logout</a>
            </html>
        ''',
    ))
    tracker = make_tracker(tmp_path)
    await tracker.login()
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == [call(
        url='http://nbl.local' + tracker._url_path['login'],
        user_agent=True,
        data={
            'username': 'bunny',
            'password': 'hunter2',
            'twofa': '',
            'login': 'Login',
        },
    )]
    assert tracker.logged_in
    assert tracker._logout_url == 'http://nbl.local/logout.php?asdfasdf'
    assert tracker._auth_key == '12345'

@pytest.mark.parametrize(
    argnames='method_name',
    argvalues=(
        '_report_login_error',
        '_store_auth_key',
        '_store_logout_url',
    ),
)
@pytest.mark.asyncio
async def test_login_dumps_html_if_handling_response_fails(method_name, tmp_path, mocker):
    response = '''
    <html>
        <input name="auth" value="12345" />
        <a href="logout.php?asdfasdf">logout</a>
    </html>
    '''
    html_dump_mock = mocker.patch('upsies.utils.html.dump')
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(return_value=response))
    tracker = make_tracker(tmp_path)
    with patch.object(tracker, method_name) as method_mock:
        method_mock.side_effect = Exception('Oooph!')
        with pytest.raises(Exception, match=r'^Oooph!$'):
            await tracker.login()
    assert not tracker.logged_in
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == [call(
        url='http://nbl.local' + tracker._url_path['login'],
        user_agent=True,
        data={
            'username': 'bunny',
            'password': 'hunter2',
            'twofa': '',
            'login': 'Login',
        }
    )]
    assert not tracker.logged_in
    assert html_dump_mock.call_args_list == [
        call(response, 'login.html'),
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
    def get_stored_response(name):
        filepath = os.path.join(
            os.path.dirname(__file__),
            'html',
            f'nbl.{name}.html',
        )
        return open(filepath, 'r').read()

    tracker = make_tracker(tmp_path)
    html = bs4.BeautifulSoup(
        markup=get_stored_response(error),
        features='html.parser',
    )
    with pytest.raises(errors.RequestError, match=rf'^Login failed: {exp_message}$'):
        tracker._report_login_error(html)


def test_logged_in(tmp_path):
    tracker = make_tracker(tmp_path)
    # tracker.logged_in must be True if "_logout_url" and "_auth_key" are set
    assert tracker.logged_in is False
    tracker._logout_url = 'asdf'
    assert tracker.logged_in is False
    tracker._auth_key = 'asdf'
    assert tracker.logged_in is True
    delattr(tracker, '_logout_url')
    assert tracker.logged_in is False
    tracker._logout_url = 'asdf'
    assert tracker.logged_in is True
    delattr(tracker, '_auth_key')
    assert tracker.logged_in is False

@pytest.mark.parametrize(
    argnames=('logout_url', 'auth_key'),
    argvalues=(
        ('http://localhost/logout.php', '12345'),
        ('http://localhost/logout.php', None),
        (None, '12345'),
        (None, None),
    ),
)
@pytest.mark.asyncio
async def test_logout(logout_url, auth_key, tmp_path, mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    tracker = make_tracker(tmp_path)
    if logout_url is not None:
        tracker._logout_url = logout_url
    if auth_key is not None:
        tracker._auth_key = auth_key
    await tracker.logout()
    if logout_url is not None:
        assert get_mock.call_args_list == [
            call(logout_url, user_agent=True),
        ]
    else:
        assert get_mock.call_args_list == []
    assert post_mock.call_args_list == []
    assert not hasattr(tracker, '_logout_url')
    assert not hasattr(tracker, '_auth_key')


@pytest.mark.asyncio
async def test_upload_without_being_logged_in(tmp_path, mocker):
    tracker = make_tracker(tmp_path)
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    metadata_mock = {'torrent': '/path/to/torrent'}
    with pytest.raises(RuntimeError, match=r'^upload\(\) called before login\(\)$'):
        await tracker.upload(metadata_mock)
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == []


@pytest.mark.asyncio
async def test_upload_succeeds(tmp_path, mocker, httpserver):
    translate_category_mock = mocker.patch(
        'upsies.trackers.nbl.Tracker._translate_category',
        Mock(return_value=b'123'),
    )

    class Handler(RequestHandler):
        def handle(self, request):
            request_seen = {
                'method': request.method,
                'User-Agent': request.headers.get('User-Agent', ''),
                'multipart/form-data': dict(request.form),
            }
            # werkzeug.Request stores files in the `files` property
            for field, filestorage in request.files.items():
                request_seen['multipart/form-data'][field] = filestorage.read()
            self.requests_seen.append(request_seen)
            # Upload form redirects to torrent page
            return Response(
                status=307,
                headers={'Location': '/torrents.php?id=123'},
            )

    handler = Handler()
    httpserver.expect_request(
        uri='/upload.php',
        method='POST',
    ).respond_with_handler(
        handler,
    )

    torrent_file = tmp_path / 'foo.torrent'
    torrent_file.write_bytes(b'mocked torrent metainfo')
    tracker = make_tracker(
        tmp_path,
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': httpserver.url_for(''),
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
    tracker._logout_url = 'logout.php'
    tracker._auth_key = 'mocked auth key'
    metadata_mock = {
        'create-torrent': (str(torrent_file),),
        'mediainfo': ('mocked mediainfo',),
        'tvmaze-id': ('12345',),
        'category': ('season',),
    }
    torrent_page_url = await tracker.upload(metadata_mock)
    assert torrent_page_url == httpserver.url_for('/torrents.php?id=123')
    assert handler.requests_seen == [{
        'method': 'POST',
        'User-Agent': f'{__project_name__}/{__version__}',
        'multipart/form-data': {
            'MAX_FILE_SIZE': '1048576',
            'auth': 'mocked auth key',
            'category': '123',
            'desc': 'mocked mediainfo',
            'file_input': b'mocked torrent metainfo',
            'fontfont': '-1',
            'fontsize': '-1',
            'genre_tags': '',
            'image': '',
            'media': 'mocked mediainfo',
            'mediaclean': '[mediainfo]mocked mediainfo[/mediainfo]',
            'submit': 'true',
            'tags': '',
            'title': '',
            'tvmazeid': '12345',
        },
    }]
    assert translate_category_mock.call_args_list == [
        call(metadata_mock['category'][0]),
    ]

@pytest.mark.asyncio
async def test_upload_finds_error_message(tmp_path, mocker, httpserver):
    mocker.patch(
        'upsies.trackers.nbl.Tracker._translate_category',
        Mock(return_value=b'123'),
    )
    html_dump_mock = mocker.patch('upsies.utils.html.dump')

    httpserver.expect_request(
        uri='/upload.php',
        method='POST',
    ).respond_with_data('''
        <html>
            <div id="messagebar">Something went wrong</div>
        </html>
    ''')

    torrent_file = tmp_path / 'foo.torrent'
    torrent_file.write_bytes(b'mocked torrent metainfo')
    tracker = make_tracker(
        tmp_path,
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': httpserver.url_for(''),
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
    tracker._logout_url = 'logout.php'
    tracker._auth_key = 'mocked auth key'
    metadata_mock = {
        'create-torrent': (str(torrent_file),),
        'mediainfo': ('mocked mediainfo',),
        'tvmaze-id': ('12345',),
        'category': ('season',),
    }
    with pytest.raises(errors.RequestError, match=r'^Upload failed: Something went wrong$'):
        await tracker.upload(metadata_mock)
    assert html_dump_mock.call_args_list == []


@pytest.mark.asyncio
async def test_upload_fails_to_find_error_message(tmp_path, mocker, httpserver):
    mocker.patch(
        'upsies.trackers.nbl.Tracker._translate_category',
        Mock(return_value=b'123'),
    )
    html_dump_mock = mocker.patch('upsies.utils.html.dump')
    response = 'unexpected html'
    httpserver.expect_request(
        uri='/upload.php',
        method='POST',
    ).respond_with_data(response)

    torrent_file = tmp_path / 'foo.torrent'
    torrent_file.write_bytes(b'mocked torrent metainfo')
    tracker = make_tracker(
        tmp_path,
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': httpserver.url_for(''),
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
    tracker._logout_url = 'logout.php'
    tracker._auth_key = 'mocked auth key'
    metadata_mock = {
        'create-torrent': (str(torrent_file),),
        'mediainfo': ('mocked mediainfo',),
        'tvmaze-id': ('12345',),
        'category': ('season',),
    }
    with pytest.raises(RuntimeError, match=(r'^Failed to find error message. '
                                            r'See upload.html for more information.$')):
        await tracker.upload(metadata_mock)
    assert html_dump_mock.call_args_list == [
        call(response, 'upload.html'),
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
    tracker = make_tracker(tmp_path)
    assert tracker._translate_category(category) == exp_category

def test_invalid_request_category(tmp_path):
    tracker = make_tracker(tmp_path)
    with pytest.raises(errors.RequestError, match=r'^Unsupported type: movie$'):
        tracker._translate_category('movie')
