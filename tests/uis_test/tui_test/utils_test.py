import asyncio
from unittest.mock import Mock, call

from upsies.uis.tui import utils


def test_Throbber_active_argument():
    throbber = utils.Throbber(callback=Mock(), active=1)
    assert throbber.active is True
    throbber = utils.Throbber(callback=Mock(), active=0)
    assert throbber.active is False

def test_Throbber_active_property(mocker):
    mocker.patch('upsies.uis.tui.utils.Throbber._iterate')
    throbber = utils.Throbber(callback=Mock())
    assert throbber.active is False
    assert throbber._iterate.call_args_list == []
    throbber.active = 1
    assert throbber.active is True
    assert throbber._iterate.call_args_list == [call()]
    throbber.active = 0
    assert throbber.active is False
    assert throbber._iterate.call_args_list == [call()]
    throbber.active = 'yes'
    assert throbber.active is True
    assert throbber._iterate.call_args_list == [call(), call()]

def test_Throbber_active_property_calls_iterate(mocker):
    call_later_mock = mocker.patch.object(asyncio.get_event_loop(), 'call_later')
    throbber = utils.Throbber(callback=Mock(), interval=0)
    assert call_later_mock.call_args_list == []
    throbber.active = True
    assert call_later_mock.call_args_list == [call(0.0, throbber._iterate)]


def test_Throbber_iterate_while_not_active(mocker):
    call_later_mock = mocker.patch.object(asyncio.get_event_loop(), 'call_later')
    cb = Mock()
    throbber = utils.Throbber(callback=cb, interval=123, states=('a', 'b', 'c'))
    throbber._iterate()
    assert cb.call_args_list == []
    assert call_later_mock.call_args_list == []
    throbber._iterate()
    assert cb.call_args_list == []
    assert call_later_mock.call_args_list == []
    throbber._iterate()
    assert cb.call_args_list == []
    assert call_later_mock.call_args_list == []

def test_Throbber_iterate_while_active(mocker):
    call_later_mock = mocker.patch.object(asyncio.get_event_loop(), 'call_later')
    cb = Mock()
    throbber = utils.Throbber(callback=cb, interval=123, states=('a', 'b', 'c'), active=False)
    assert cb.call_args_list == []
    assert call_later_mock.call_args_list == []
    throbber.active = True
    assert cb.call_args_list == [
        call('a'),
    ]
    assert call_later_mock.call_args_list == [
        call(123.0, throbber._iterate),
    ]
    throbber._iterate()
    assert cb.call_args_list == [
        call('a'),
        call('b'),
    ]
    assert call_later_mock.call_args_list == [
        call(123.0, throbber._iterate),
        call(123.0, throbber._iterate),
    ]
    throbber._iterate()
    assert cb.call_args_list == [
        call('a'),
        call('b'),
        call('c'),
    ]
    assert call_later_mock.call_args_list == [
        call(123.0, throbber._iterate),
        call(123.0, throbber._iterate),
        call(123.0, throbber._iterate),
    ]
