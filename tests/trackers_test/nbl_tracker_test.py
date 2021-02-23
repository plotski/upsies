import os
from unittest.mock import Mock, call, patch

import bs4
import pytest
from pytest_httpserver.httpserver import Response

from upsies import __project_name__, __version__, errors
from upsies.trackers.nbl import NblTracker


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


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


def test_name_attribute():
    assert NblTracker.name == 'nbl'


def test_label_attribute():
    assert NblTracker.label == 'NBL'


@pytest.mark.asyncio
async def test_login_does_nothing_if_already_logged_in(mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    tracker = NblTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://nbl.local',
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
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
async def test_login_succeeds(mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(
        return_value='''
            <html>
                <input name="auth" value="12345" />
                <a href="logout.php?asdfasdf">logout</a>
            </html>
        ''',
    ))
    tracker = NblTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://nbl.local',
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
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
async def test_login_dumps_html_if_handling_response_fails(method_name, mocker):
    response = '''
    <html>
        <input name="auth" value="12345" />
        <a href="logout.php?asdfasdf">logout</a>
    </html>
    '''
    html_dump_mock = mocker.patch('upsies.utils.html.dump')
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(return_value=response))
    tracker = NblTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://nbl.local',
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
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
    argnames='page, exp_message',
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
def test_report_login_error(page, exp_message, get_html_page):
    tracker = NblTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://nbl.local',
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
    html = bs4.BeautifulSoup(
        markup=get_html_page('nbl', page),
        features='html.parser',
    )
    with pytest.raises(errors.RequestError, match=rf'^Login failed: {exp_message}$'):
        tracker._report_login_error(html)


def test_logged_in():
    tracker = NblTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://nbl.local',
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
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
async def test_logout(logout_url, auth_key, mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    tracker = NblTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://nbl.local',
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
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
async def test_upload_without_being_logged_in(mocker):
    tracker = NblTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://nbl.local',
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    metadata_mock = {'torrent': '/path/to/torrent'}
    with pytest.raises(RuntimeError, match=r'^upload\(\) called before login\(\)$'):
        await tracker.upload(metadata_mock)
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == []


@pytest.mark.parametrize(
    argnames='ignore_dupes, exp_additional_data',
    argvalues=(
        (False, {}),
        (True, {'ignoredupes': '1'}),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_upload_succeeds(ignore_dupes, exp_additional_data, tmp_path, mocker, httpserver):
    translate_category_mock = mocker.patch(
        'upsies.trackers.nbl.NblTracker._translate_category',
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
    tracker = NblTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': httpserver.url_for(''),
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
        cli_args=Mock(
            ignore_dupes=ignore_dupes,
        ),
    )
    tracker._logout_url = 'logout.php'
    tracker._auth_key = 'mocked auth key'
    metadata_mock = {
        'torrent': (str(torrent_file),),
        'mediainfo': ('mocked mediainfo',),
        'tvmaze-id': ('12345',),
        'category': ('season',),
    }
    torrent_page_url = await tracker.upload(metadata_mock)
    assert torrent_page_url == httpserver.url_for('/torrents.php?id=123')
    exp_form_data = {
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
    }
    exp_form_data.update(exp_additional_data)
    assert handler.requests_seen == [{
        'method': 'POST',
        'User-Agent': f'{__project_name__}/{__version__}',
        'multipart/form-data': exp_form_data,
    }]
    assert translate_category_mock.call_args_list == [
        call(metadata_mock['category'][0]),
    ]

@pytest.mark.asyncio
async def test_upload_finds_error_message(tmp_path, mocker, httpserver):
    mocker.patch(
        'upsies.trackers.nbl.NblTracker._translate_category',
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
    tracker = NblTracker(
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
        'torrent': (str(torrent_file),),
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
        'upsies.trackers.nbl.NblTracker._translate_category',
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
    tracker = NblTracker(
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
        'torrent': (str(torrent_file),),
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
def test_valid_request_category(category, exp_category):
    tracker = NblTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://nbl.local',
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
    assert tracker._translate_category(category) == exp_category

def test_invalid_request_category():
    tracker = NblTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://nbl.local',
            'announce': 'http://nbl.local/announce',
            'exclude': 'some files',
        },
    )
    with pytest.raises(errors.RequestError, match=r'^Unsupported type: movie$'):
        tracker._translate_category('movie')
