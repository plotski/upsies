import re
from unittest.mock import Mock, call

import bs4
import pytest

from upsies import __project_name__, errors
from upsies.trackers.bb import BbTracker, BbTrackerConfig, BbTrackerJobs
from upsies.utils.http import Result


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_name_attribute():
    assert BbTracker.name == 'bb'


def test_label_attribute():
    assert BbTracker.label == 'bB'


def test_TrackerConfig_attribute():
    assert BbTracker.TrackerConfig is BbTrackerConfig


def test_TrackerJobs_attribute():
    assert BbTracker.TrackerJobs is BbTrackerJobs


@pytest.mark.asyncio
async def test_login_succeeds(mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(
        return_value='''
            <html>
                <a href="somewhere">Go somewhere</a>
                <a href="logout.php?auth=d34db33f">Logout</a>
                <a href="somewhere/else">Go somewhere else</a>
            </html>
        ''',
    ))
    sleep_mock = mocker.patch('asyncio.sleep', AsyncMock())
    tracker = BbTracker(
        options={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://bb.local',
        },
    )
    assert not tracker.is_logged_in
    await tracker.login()
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == [call(
        url='http://bb.local' + tracker._url_path['login'],
        user_agent=True,
        data={
            'username': 'bunny',
            'password': 'hunter2',
            'login': 'Log In!',
        },
    )]
    assert sleep_mock.call_args_list == []
    assert tracker.is_logged_in
    assert tracker._auth_token == 'd34db33f'

@pytest.mark.parametrize(
    argnames='credentials, exp_error',
    argvalues=(
        ({}, 'No username configured'),
        ({'username': 'foo'}, 'No password configured'),
        ({'password': 'bar'}, 'No username configured'),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_login_with_incomplete_login_credentials(credentials, exp_error, mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    sleep_mock = mocker.patch('asyncio.sleep', AsyncMock())
    tracker = BbTracker(
        options={**{'base_url': 'http://bb.local'}, **credentials}
    )
    assert not tracker.is_logged_in
    with pytest.raises(errors.RequestError, match=rf'^Login failed: {exp_error}$'):
        await tracker.login()
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == []
    assert sleep_mock.call_args_list == []
    assert not tracker.is_logged_in
    assert not hasattr(tracker, '_auth_token')

@pytest.mark.asyncio
async def test_login_fails_and_finds_error_message(mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(
        return_value='''
            <html>
                <form id="loginform"><font color="red">The error message</font></form>
            </html>
        ''',
    ))
    sleep_mock = mocker.patch('asyncio.sleep', AsyncMock())
    tracker = BbTracker(
        options={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://bb.local',
        },
    )
    assert not tracker.is_logged_in
    with pytest.raises(errors.RequestError, match=r'^Login failed: The error message$'):
        await tracker.login()
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == [call(
        url='http://bb.local' + tracker._url_path['login'],
        user_agent=True,
        data={
            'username': 'bunny',
            'password': 'hunter2',
            'login': 'Log In!',
        },
    )]
    assert sleep_mock.call_args_list == []
    assert not tracker.is_logged_in
    assert not hasattr(tracker, '_auth_token')

@pytest.mark.asyncio
async def test_login_fails_and_does_not_find_error_message(mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(
        return_value='''
            <html>
                <form id="loginform"><p>Obscured error message</p></form>
            </html>
        ''',
    ))
    sleep_mock = mocker.patch('asyncio.sleep', AsyncMock())
    mocker.patch('upsies.utils.html.dump')
    tracker = BbTracker(
        options={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://bb.local',
        },
    )
    assert not tracker.is_logged_in
    with pytest.raises(errors.RequestError, match=r'^Login failed: No error message found. See login.html.$'):
        await tracker.login()
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == [call(
        url='http://bb.local' + tracker._url_path['login'],
        user_agent=True,
        data={
            'username': 'bunny',
            'password': 'hunter2',
            'login': 'Log In!',
        },
    )]
    assert sleep_mock.call_args_list == []
    assert not tracker.is_logged_in
    assert not hasattr(tracker, '_auth_token')

@pytest.mark.asyncio
async def test_login_does_nothing_if_already_logged_in(mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    sleep_mock = mocker.patch('asyncio.sleep', AsyncMock())
    tracker = BbTracker()
    tracker._auth_token = 'something'
    assert tracker.is_logged_in
    await tracker.login()
    assert tracker.is_logged_in
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == []
    assert sleep_mock.call_args_list == []
    assert tracker._auth_token == 'something'

@pytest.mark.asyncio
async def test_login_bug_workaround_retries_login_successfully(mocker):
    html_logged_in = '''
        <html>
            <a href="somewhere">Go somewhere</a>
            <a href="logout.php?auth=d34db33f">Logout</a>
            <a href="somewhere/else">Go somewhere else</a>
        </html>
    '''
    html_login_bug = '''<html></html>'''
    get_mock = mocker.patch.object(BbTracker, '_max_login_attempts', 4)
    responses = ([html_login_bug] * (BbTracker._max_login_attempts - 1)
                 + [html_logged_in])
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(
        side_effect=responses,
    ))
    sleep_mock = mocker.patch('asyncio.sleep', AsyncMock())
    tracker = BbTracker(
        options={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://bb.local',
        },
    )
    assert not tracker.is_logged_in
    await tracker.login()
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == [call(
        url='http://bb.local' + tracker._url_path['login'],
        user_agent=True,
        data={
            'username': 'bunny',
            'password': 'hunter2',
            'login': 'Log In!',
        },
    )] * BbTracker._max_login_attempts
    assert sleep_mock.call_args_list == [call(1), call(2)]
    assert tracker.is_logged_in
    assert tracker._auth_token == 'd34db33f'

@pytest.mark.asyncio
async def test_login_bug_workaround_exceeds_max_attempts(mocker):
    html_logged_in = '''
        <html>
            <a href="somewhere">Go somewhere</a>
            <a href="logout.php?auth=d34db33f">Logout</a>
            <a href="somewhere/else">Go somewhere else</a>
        </html>
    '''
    html_login_bug = '''<html></html>'''
    get_mock = mocker.patch.object(BbTracker, '_max_login_attempts', 10)
    responses = ([html_login_bug] * BbTracker._max_login_attempts
                 + [html_logged_in])
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(
        side_effect=responses,
    ))
    sleep_mock = mocker.patch('asyncio.sleep', AsyncMock())
    tracker = BbTracker(
        options={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://bb.local',
        },
    )
    assert not tracker.is_logged_in
    with pytest.raises(errors.RequestError, match=r'^Login failed: Giving up after encountering login bug 10 times$'):
        await tracker.login()
    assert get_mock.call_args_list == []
    assert post_mock.call_args_list == [call(
        url='http://bb.local' + tracker._url_path['login'],
        user_agent=True,
        data={
            'username': 'bunny',
            'password': 'hunter2',
            'login': 'Log In!',
        },
    )] * BbTracker._max_login_attempts
    assert sleep_mock.call_args_list == [
        call(1), call(2), call(2), call(2), call(3), call(3), call(3), call(3),
    ]
    assert not tracker.is_logged_in
    assert not hasattr(tracker, '_auth_token')


@pytest.mark.parametrize(
    argnames='html, exp_auth_token',
    argvalues=(
        ('<html><img src="logout.php?foo=d34db33f">Logout</img></html>', None),
        ('<html><a>Logout</a></html>', None),
        ('<html><a href="logout.php?foo=d34db33f">Logout</a></html>', None),
        ('<html><a href="logfoo.php?auth=d34db33f">Logout</a></html>', None),
        ('<html><a href="logout.php?auth=not_a_hash">Logout</a></html>', None),
        ('<html><a href="logout.php?auth=d34db33f">Logout</a></html>', 'd34db33f'),
    ),
    ids=lambda v: str(v),
)
def test_get_auth_token(html, exp_auth_token):
    doc = bs4.BeautifulSoup(html, features='html.parser')
    assert BbTracker._get_auth_token(doc) == exp_auth_token


@pytest.mark.parametrize(
    argnames='token, exp_exception',
    argvalues=(
        ('mock token', None),
        (None, RuntimeError('Failed to find authentication token')),
    ),
    ids=lambda v: str(v),
)
def test_store_auth_token(token, exp_exception, mocker):
    mocker.patch('upsies.trackers.bb.BbTracker._get_auth_token', return_value=token)
    mock_doc = object()
    tracker = BbTracker()
    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            tracker._store_auth_token(mock_doc)
    else:
        tracker._store_auth_token(mock_doc)
        assert tracker._auth_token == token


@pytest.mark.parametrize(
    argnames='page, exp_message',
    argvalues=(
        pytest.param(
            'login.auth-failed',
            r'You entered an invalid password\.',
            id='login.auth-failed',
        ),
        pytest.param(
            'login.max-attempts',
            (r'You are banned from logging in for another 4 hours and 42 minutes'),
            id='login.max-attempts',
        ),
        pytest.param(
            'login.no-error',
            (r'No error message found\. See login\.html\.'),
            id='login.no-error',
        ),
    ),
)
def test_raise_login_error(page, exp_message, get_html_page, mocker):
    html_dump_mock = mocker.patch('upsies.utils.html.dump')
    tracker = BbTracker()
    html = bs4.BeautifulSoup(
        markup=get_html_page('bb', page),
        features='html.parser',
    )
    with pytest.raises(errors.RequestError, match=rf'^Login failed: {exp_message}$'):
        tracker._raise_login_error(html)
    if page == 'login.no-error':
        assert html_dump_mock.call_args_list == [call(html, 'login.html')]
    else:
        assert html_dump_mock.call_args_list == []


def test_logged_in():
    tracker = BbTracker()
    assert tracker.is_logged_in is False
    tracker._auth_token = 'asdf'
    assert tracker.is_logged_in is True
    tracker._auth_token = ''
    assert tracker.is_logged_in is False
    delattr(tracker, '_auth_token')
    assert tracker.is_logged_in is False


@pytest.mark.parametrize('auth_token', ('asdf', None))
@pytest.mark.asyncio
async def test_logout(auth_token, mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    tracker = BbTracker(options={'base_url': 'http://bb.local'})
    if auth_token:
        tracker._auth_token = auth_token
    await tracker.logout()
    if auth_token:
        assert get_mock.call_args_list == [call(
            url='http://bb.local' + BbTracker._url_path['logout'],
            params={'auth': auth_token},
            user_agent=True,
        )]
    else:
        assert get_mock.call_args_list == []
    assert post_mock.call_args_list == []
    assert not hasattr(tracker, '_auth_token')


@pytest.mark.asyncio
async def test_get_announce_url_from_options(mocker):
    tracker = BbTracker(options={'base_url': 'http://bb.local',
                                 'announce_url': 'https://bb.local:123/d34db33f/announce'})

    mocks = AsyncMock(
        get=mocker.patch('upsies.utils.http.get', AsyncMock(
            return_value='you should never get this response',
        )),
        post=mocker.patch('upsies.utils.http.post', AsyncMock()),
        login=AsyncMock(),
        logout=AsyncMock(),
    )
    mocker.patch.object(tracker, 'login', mocks.login)
    mocker.patch.object(tracker, 'logout', mocks.logout)

    announce_url = await tracker.get_announce_url()
    assert announce_url == 'https://bb.local:123/d34db33f/announce'
    assert mocks.mock_calls == []

@pytest.mark.asyncio
async def test_get_announce_url_succeeds(mocker):
    tracker = BbTracker(options={'base_url': 'http://bb.local'})

    mocks = AsyncMock(
        get=mocker.patch('upsies.utils.http.get', AsyncMock(
            return_value='''
            <html>
                <input type="text" value="https://bb.local:123/l33tb34f/announce">
            </html>
            ''',
        )),
        post=mocker.patch('upsies.utils.http.post', AsyncMock()),
        login=AsyncMock(),
        logout=AsyncMock(),
    )
    mocker.patch.object(tracker, 'login', mocks.login)
    mocker.patch.object(tracker, 'logout', mocks.logout)

    announce_url = await tracker.get_announce_url()
    assert announce_url == 'https://bb.local:123/l33tb34f/announce'
    assert mocks.mock_calls == [
        call.login(),
        call.get('http://bb.local' + BbTracker._url_path['upload'], cache=False, user_agent=True),
        call.logout(),
    ]

@pytest.mark.asyncio
async def test_get_announce_url_fails(mocker):
    tracker = BbTracker(options={'base_url': 'http://bb.local'})

    mocks = AsyncMock(
        get=mocker.patch('upsies.utils.http.get', AsyncMock(
            return_value='<html>foo</html>',
        )),
        post=mocker.patch('upsies.utils.http.post', AsyncMock()),
        login=AsyncMock(),
        logout=AsyncMock(),
    )
    mocker.patch.object(tracker, 'login', mocks.login)
    mocker.patch.object(tracker, 'logout', mocks.logout)

    exp_cmd = f'{__project_name__} set trackers.{tracker.name}.announce_url <YOUR URL>'
    with pytest.raises(errors.RequestError, match=rf'^Failed to find announce URL - set it manually: {exp_cmd}$'):
        await tracker.get_announce_url()
    assert mocks.mock_calls == [
        call.login(),
        call.get('http://bb.local' + BbTracker._url_path['upload'], cache=False, user_agent=True),
        call.logout(),
    ]


@pytest.mark.asyncio
async def test_upload_makes_expected_request(mocker):
    response = Result(text='', bytes=b'', headers={'Location': 'torrents.php?id=123'})
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(return_value=response))
    tracker = BbTracker(options={'base_url': 'http://bb.local'})
    tracker_jobs_mock = Mock()
    torrent_page_url = await tracker.upload(tracker_jobs_mock)
    assert torrent_page_url == 'http://bb.local/torrents.php?id=123'
    assert post_mock.call_args_list == [call(
        url='http://bb.local' + BbTracker._url_path['upload'],
        cache=False,
        user_agent=True,
        follow_redirects=False,
        files={'file_input': {
            'file': tracker_jobs_mock.torrent_filepath,
            'mimetype': 'application/octet-stream',
        }},
        data=tracker_jobs_mock.post_data,
    )]

@pytest.mark.parametrize('headers', ({'Location': 'somewhere.php'}, {}))
@pytest.mark.parametrize(
    argnames='page, exp_message',
    argvalues=(
        pytest.param(
            'upload.error1',
            r'This is a red error message!',
            id='upload.error1',
        ),
        pytest.param(
            'upload.error2',
            r'The exact same torrent file already exists on the site!',
            id='upload.error2',
        ),
    ),
)
@pytest.mark.asyncio
async def test_upload_finds_error_error_message(page, exp_message, headers, get_html_page, mocker):
    response = Result(
        text=get_html_page('bb', page),
        bytes=b'not relevant',
        headers=headers,
    )
    mocker.patch('upsies.utils.http.post', AsyncMock(return_value=response))
    tracker = BbTracker(
        options={
            'base_url': 'http://bb.local',
        },
    )
    tracker_jobs_mock = Mock()
    with pytest.raises(errors.RequestError, match=rf'^Upload failed: {exp_message}$'):
        await tracker.upload(tracker_jobs_mock)

@pytest.mark.asyncio
async def test_upload_finds_empty_error_message(mocker):
    response = Result(
        text='''
        <html>
        <body>
        <p style="color: red;text-align:center;">

        </p>
        </body>
        </html>
        ''',
        bytes=b'not relevant',
    )
    html_dump_mock = mocker.patch('upsies.utils.html.dump')
    mocker.patch('upsies.utils.http.post', AsyncMock(return_value=response))
    tracker = BbTracker(options={'base_url': 'http://bb.local'})
    tracker_jobs_mock = Mock()
    with pytest.raises(RuntimeError, match=r'^Failed to find error message\. See upload\.html\.$'):
        await tracker.upload(tracker_jobs_mock)
    assert html_dump_mock.call_args_list == [call(response, 'upload.html')]

@pytest.mark.parametrize('headers', ({'Location': 'somewhere.php'}, {}))
@pytest.mark.parametrize(
    argnames='page, exp_message',
    argvalues=(
        pytest.param(
            'upload.warning1',
            r'foo',
            id='upload.warning1',
        ),
    ),
)
@pytest.mark.asyncio
async def test_upload_finds_warning_message(page, exp_message, headers, get_html_page, mocker):
    response = Result(
        text=get_html_page('bb', page),
        bytes=b'not relevant',
        headers=headers,
    )
    mocker.patch('upsies.utils.http.post', AsyncMock(return_value=response))
    tracker = BbTracker(
        options={
            'base_url': 'http://bb.local',
        },
    )
    tracker_jobs_mock = Mock()
    mocker.patch.object(tracker, 'warn')
    torrent_page_url = await tracker.upload(tracker_jobs_mock)
    assert torrent_page_url is None
    assert tracker.warn.call_args_list == [
        call('The torrent did not have the correct announce URL.'),
        call('The mediainfo was not encoded in ROT13.'),
        call('Your mom.'),
    ]

@pytest.mark.parametrize(
    argnames='html_string',
    argvalues=(
        ('<html><body><h2>Warning</h2>Your torrent has been uploaded however, blablabla</body></html>',),
    ),
)
@pytest.mark.asyncio
async def test_upload_handles_incomplete_warning_message(html_string, mocker):
    response = Result(
        text=html_string,
        bytes=b'not relevant',
    )
    mocker.patch('upsies.utils.http.post', AsyncMock(return_value=response))
    tracker = BbTracker(
        options={
            'base_url': 'http://bb.local',
        },
    )
    tracker_jobs_mock = Mock()
    html_dump_mock = mocker.patch('upsies.utils.html.dump')
    mocker.patch.object(tracker, 'warn')
    with pytest.raises(RuntimeError, match=r'^Failed to find error message\. See upload\.html\.$'):
        await tracker.upload(tracker_jobs_mock)
    assert html_dump_mock.call_args_list == [call(response, 'upload.html')]
    assert tracker.warn.call_args_list == []

@pytest.mark.asyncio
async def test_upload_fails_to_find_error_or_warning_message(mocker):
    response = Result(
        text='''
        <html>
        <body>
        </body>
        </html>
        ''',
        bytes=b'not relevant',
    )
    html_dump_mock = mocker.patch('upsies.utils.html.dump')
    mocker.patch('upsies.utils.http.post', AsyncMock(return_value=response))
    tracker = BbTracker(options={'base_url': 'http://bb.local'})
    tracker_jobs_mock = Mock()
    with pytest.raises(RuntimeError, match=r'^Failed to find error message\. See upload\.html\.$'):
        await tracker.upload(tracker_jobs_mock)
    assert html_dump_mock.call_args_list == [call(response, 'upload.html')]
