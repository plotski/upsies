from unittest.mock import AsyncMock, Mock, PropertyMock, call

import aiobtclientapi

from upsies.trackers import base


def make_MockTracker(**kwargs):
    class MockTracker(base.TrackerBase):
        name = 'asdf'
        label = 'AsdF'
        TrackerJobs = PropertyMock()
        TrackerConfig = PropertyMock()
        login = AsyncMock()
        logout = AsyncMock()
        is_logged_in = PropertyMock()
        get_announce_url = AsyncMock()
        upload = AsyncMock()

    return MockTracker(**kwargs)


def test_options():
    options = {'username': 'foo', 'password': 'bar'}
    tracker = make_MockTracker(options=options)
    assert tracker.options is options


def test_signals():
    tracker = make_MockTracker()
    cb = Mock()
    tracker.signal.register('warning', cb.warn)
    tracker.signal.register('error', cb.error)
    tracker.signal.register('exception', cb.exception)
    tracker.warn('foo')
    assert cb.mock_calls == [call.warn('foo')]
    tracker.error('bar')
    assert cb.mock_calls == [call.warn('foo'), call.error('bar')]
    tracker.exception('baz')
    assert cb.mock_calls == [call.warn('foo'), call.error('bar'), call.exception('baz')]


def test_generate_setup_howto_makes_expected_calls(mocker):
    _Howto_mock = mocker.patch('upsies.trackers.base._Howto')
    evaluate_fstring_mock = mocker.patch('upsies.utils.string.evaluate_fstring')
    tracker = make_MockTracker()
    return_value = type(tracker).generate_setup_howto()
    assert return_value is evaluate_fstring_mock.return_value
    assert _Howto_mock.call_args_list == [call(tracker_cls=type(tracker))]

def test_generate_setup_howto_populates_namespace_expectedly(mocker):
    tracker = make_MockTracker()
    type(tracker).setup_howto_template = '{isinstance(howto, _Howto)}'
    assert type(tracker).generate_setup_howto() == 'True'


def test_Howto_current_section_and_bump_section():
    howto = base._Howto(tracker_cls=type(make_MockTracker()))
    for i in range(10):
        for _ in range(3):
            assert howto.current_section == i

        assert howto.bump_section == ''

        for _ in range(3):
            assert howto.current_section == i + 1

def test_Howto_introduction():
    howto = base._Howto(tracker_cls=type(make_MockTracker()))
    howto._section = 123
    assert howto.introduction == (
        '123. How To Read This Howto\n'
        '\n'
        '   123.1 Words in ALL_CAPS_AND_WITH_UNDERSCORES are placeholders.\n'
        '   123.2 Everything after "$" is a terminal command.'
    )

def test_Howto_autoseed():
    tracker_cls = type(make_MockTracker())
    howto = base._Howto(tracker_cls=tracker_cls)
    howto._section = 7
    assert howto.autoseed == (
        '7. Add Uploaded Torrents To Client (Optional)\n'
        '\n'
        '   7.1 Specify which client to add uploaded torrents to.\n'
        f'       $ upsies set trackers.{tracker_cls.name}.add-to CLIENT_NAME\n'
        f'       Supported clients: {", ".join(n for n in aiobtclientapi.client_names())}\n'
        '\n'
        '   7.2 Specify your client connection.\n'
        '       $ upsies set clients.CLIENT_NAME.url URL\n'
        '       $ upsies set clients.CLIENT_NAME.username USERNAME\n'
        '       $ upsies set clients.CLIENT_NAME.password PASSWORD\n'
        '\n'
        '8. Copy Uploaded Torrents To Directory (Optional)\n'
        '\n'
        f'   $ upsies set trackers.{tracker_cls.name}.copy-to /path/to/directory'
    )

def test_Howto_upload():
    tracker_cls = type(make_MockTracker())
    howto = base._Howto(tracker_cls=tracker_cls)
    howto._section = 123
    assert howto.upload == (
        '123. Upload\n'
        '\n'
        f'   $ upsies submit {tracker_cls.name} /path/to/content'
    )
