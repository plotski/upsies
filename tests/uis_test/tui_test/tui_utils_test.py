from unittest.mock import Mock, call

import pytest

from upsies.uis.tui import utils


@pytest.mark.parametrize(
    argnames='stdin_isatty, stdout_isatty, stderr_isatty',
    argvalues=(
        (False, False, False),
        (False, False, True),
        (False, True, False),
        (False, True, True),
        (True, False, False),
        (True, False, True),
        (True, True, False),
        (True, True, True),
    ),
)
@pytest.mark.parametrize(
    argnames='stdin, stdout, stderr',
    argvalues=(
        (None, None, None),
        (None, None, Mock()),
        (None, None, Mock()),
        (None, Mock(), None),
        (None, Mock(), Mock()),
        (Mock(), None, None),
        (Mock(), None, Mock()),
        (Mock(), Mock(), None),
        (Mock(), Mock(), Mock()),
    ),
)
def test_is_tty(stdin, stdout, stderr, stdin_isatty, stdout_isatty, stderr_isatty, mocker):
    if stdin:
        stdin.isatty = lambda: stdin_isatty
    if stdout:
        stdout.isatty = lambda: stdout_isatty
    if stderr:
        stderr.isatty = lambda: stderr_isatty
    mocker.patch('sys.stdin', stdin)
    mocker.patch('sys.stdout', stdout)
    mocker.patch('sys.stderr', stderr)

    if not stdin or not stdin.isatty():
        exp_is_tty = False
    elif (stdout and stdout.isatty()) or (stderr and stderr.isatty()):
        exp_is_tty = True
    else:
        exp_is_tty = False

    assert utils.is_tty() is exp_is_tty


@pytest.mark.asyncio  # Prevent "RuntimeError: no running event loop"
async def test_Throbber_active_argument():
    throbber = utils.Throbber(active=1)
    assert throbber.active is True
    throbber = utils.Throbber(active=0)
    assert throbber.active is False

@pytest.mark.asyncio  # Prevent "RuntimeError: no running event loop"
async def test_Throbber_active_property(mocker):
    mocker.patch('upsies.uis.tui.utils.Throbber._iterate')
    throbber = utils.Throbber()
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

@pytest.mark.asyncio  # Prevent "RuntimeError: no running event loop"
async def test_Throbber_active_property_calls_iterate(mocker, event_loop):
    throbber = utils.Throbber(interval=0)
    call_later_mock = mocker.patch.object(throbber._loop, 'call_later')
    assert call_later_mock.call_args_list == []
    throbber.active = True
    assert call_later_mock.call_args_list == [call(0.0, throbber._iterate)]


@pytest.mark.asyncio  # Prevent "RuntimeError: no running event loop"
async def test_Throbber_iterate_while_not_active(mocker):
    cb = Mock()
    throbber = utils.Throbber(callback=cb, interval=123, states=('a', 'b', 'c'))
    call_later_mock = mocker.patch.object(throbber._loop, 'call_later')
    throbber._iterate()
    assert cb.call_args_list == []
    assert call_later_mock.call_args_list == []
    throbber._iterate()
    assert cb.call_args_list == []
    assert call_later_mock.call_args_list == []
    throbber._iterate()
    assert cb.call_args_list == []
    assert call_later_mock.call_args_list == []


@pytest.mark.asyncio  # Prevent "RuntimeError: no running event loop"
async def test_Throbber_iterate_while_active(mocker):
    cb = Mock()
    throbber = utils.Throbber(callback=cb, interval=123, states=('a', 'b', 'c'),
                              active=False, format='<{throbber}>')
    call_later_mock = mocker.patch.object(throbber._loop, 'call_later')
    assert cb.call_args_list == []
    assert call_later_mock.call_args_list == []
    throbber.active = True
    assert cb.call_args_list == [
        call('<a>'),
    ]
    assert call_later_mock.call_args_list == [
        call(123.0, throbber._iterate),
    ]
    throbber._iterate()
    assert cb.call_args_list == [
        call('<a>'),
        call('<b>'),
    ]
    assert call_later_mock.call_args_list == [
        call(123.0, throbber._iterate),
        call(123.0, throbber._iterate),
    ]
    throbber._iterate()
    assert cb.call_args_list == [
        call('<a>'),
        call('<b>'),
        call('<c>'),
    ]
    assert call_later_mock.call_args_list == [
        call(123.0, throbber._iterate),
        call(123.0, throbber._iterate),
        call(123.0, throbber._iterate),
    ]
