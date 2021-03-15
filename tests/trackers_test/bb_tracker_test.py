import re
from unittest.mock import Mock, call

import bs4
import pytest

from upsies import errors
from upsies.trackers.bb import BbTracker, BbTrackerConfig
from upsies.trackers.bb.movie import MovieBbTrackerJobs
from upsies.trackers.bb.series import SeriesBbTrackerJobs
from upsies.utils.release import ReleaseType


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


@pytest.mark.parametrize(
    argnames='release_type, exp_TrackerJobs_subclass',
    argvalues=(
        (ReleaseType.movie, MovieBbTrackerJobs),
        (ReleaseType.season, SeriesBbTrackerJobs),
        (ReleaseType.episode, SeriesBbTrackerJobs),
    ),
    ids=lambda v: str(v),
)
def test_TrackerJobs_propery_from_cli_args(release_type, exp_TrackerJobs_subclass):
    tracker = BbTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://bb.local',
        },
        cli_args=Mock(type=release_type),
    )
    assert tracker.TrackerJobs is exp_TrackerJobs_subclass

@pytest.mark.parametrize(
    argnames='release_type, exp_TrackerJobs_subclass',
    argvalues=(
        (ReleaseType.movie, MovieBbTrackerJobs),
        (ReleaseType.season, SeriesBbTrackerJobs),
        (ReleaseType.episode, SeriesBbTrackerJobs),
    ),
    ids=lambda v: str(v),
)
def test_TrackerJobs_propery_from_ReleaseInfo(release_type, exp_TrackerJobs_subclass, mocker):
    mocker.patch('upsies.utils.release.ReleaseInfo', return_value={'type': release_type})
    tracker = BbTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://bb.local',
        },
        cli_args=Mock(type=None),
    )
    assert tracker.TrackerJobs is exp_TrackerJobs_subclass


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
        config={
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
        config={
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
    tracker = BbTracker(
        config={
            'username': 'bunny',
            'password': 'hunter2',
            'base_url': 'http://bb.local',
        },
    )
    assert not tracker.is_logged_in
    with pytest.raises(errors.RequestError, match=r'^Login failed: No error message found$'):
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
    index_logged_in = '''
        <html>
            <a href="somewhere">Go somewhere</a>
            <a href="logout.php?auth=d34db33f">Logout</a>
            <a href="somewhere/else">Go somewhere else</a>
        </html>
    '''
    index_login_bug = '''<html></html>'''
    get_mock = mocker.patch.object(BbTracker, '_max_login_attempts', 4)
    responses = ([index_login_bug] * (BbTracker._max_login_attempts - 1)
                 + [index_logged_in])
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(
        side_effect=responses,
    ))
    sleep_mock = mocker.patch('asyncio.sleep', AsyncMock())
    tracker = BbTracker(
        config={
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
    index_logged_in = '''
        <html>
            <a href="somewhere">Go somewhere</a>
            <a href="logout.php?auth=d34db33f">Logout</a>
            <a href="somewhere/else">Go somewhere else</a>
        </html>
    '''
    index_login_bug = '''<html></html>'''
    get_mock = mocker.patch.object(BbTracker, '_max_login_attempts', 10)
    responses = ([index_login_bug] * BbTracker._max_login_attempts
                 + [index_logged_in])
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock())
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock(
        side_effect=responses,
    ))
    sleep_mock = mocker.patch('asyncio.sleep', AsyncMock())
    tracker = BbTracker(
        config={
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
        call(1), call(2), call(2), call(2), call(3), call(4), call(4), call(5),
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
    ),
)
def test_raise_login_error(page, exp_message, get_html_page):
    tracker = BbTracker()
    html = bs4.BeautifulSoup(
        markup=get_html_page('bb', page),
        features='html.parser',
    )
    with pytest.raises(errors.RequestError, match=rf'^Login failed: {exp_message}$'):
        tracker._raise_login_error(html)


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
    tracker = BbTracker(
        config={
            'base_url': 'http://bb.local',
        },
    )
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
async def test_get_announce_url_succeeds(mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock(
        return_value='''
        <html>
            <input type="text" value="https://bb.local:123/d34db33f/announce">
        </html>
    ''',
    ))
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    tracker = BbTracker(
        config={
            'base_url': 'http://bb.local',
        },
    )
    announce_url = await tracker.get_announce_url()
    assert announce_url == 'https://bb.local:123/d34db33f/announce'
    assert get_mock.call_args_list == [
        call('http://bb.local' + BbTracker._url_path['upload'], cache=False, user_agent=True),
    ]
    assert post_mock.call_args_list == []

@pytest.mark.asyncio
async def test_get_announce_url_fails(mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock(
        return_value='<html>foo</html> ',
    ))
    post_mock = mocker.patch('upsies.utils.http.post', AsyncMock())
    tracker = BbTracker(
        config={
            'base_url': 'http://bb.local',
        },
    )
    assert await tracker.get_announce_url() is None
    assert get_mock.call_args_list == [
        call('http://bb.local' + BbTracker._url_path['upload'], cache=False, user_agent=True),
    ]
    assert post_mock.call_args_list == []
