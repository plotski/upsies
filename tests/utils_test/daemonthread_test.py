import asyncio
import threading
from unittest.mock import Mock, call, patch

import pytest

from upsies.utils.daemon import DaemonThread


class FooThread(DaemonThread):
    def work(self):
        pass

@pytest.fixture
def thread():
    return FooThread()


@pytest.mark.parametrize('method', DaemonThread.__abstractmethods__)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in DaemonThread.__abstractmethods__}
    del attrs[method]
    cls = type('Foo', (DaemonThread,), attrs)
    # Python 3.9 changed "methods" to "method"
    exp_msg = rf"^Can't instantiate abstract class Foo with abstract methods? {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def test_is_alive_before_thread_exists(thread):
    assert not hasattr(thread, '_thread')
    assert thread.is_alive is False

@pytest.mark.parametrize('is_alive', (True, False), ids=('started', 'not_started'))
def test_is_alive_after_thread_exists(is_alive, thread):
    thread._thread = Mock(is_alive=Mock(return_value=is_alive))
    assert thread.is_alive is is_alive


def test_start_can_be_called_multiple_times(thread):
    assert thread.is_alive is False
    thread.start()
    assert thread.is_alive is True
    thread.start()
    assert thread.is_alive is True

@patch('upsies.utils.daemon.threading.Thread')
def test_start_initializes(Thread_mock, thread):
    thread.start()
    assert thread._finish_work is False
    assert thread._unhandled_exception is None
    assert isinstance(thread._unblock_event, threading.Event)
    assert thread._thread is Thread_mock.return_value
    assert Thread_mock.call_args_list == [call(
        target=thread._run,
        daemon=True,
        name=type(thread).__name__,
    )]


def test_stop_before_initialization(thread):
    with patch.object(thread, 'unblock'):
        thread.stop()
        assert thread.unblock.call_args_list == []
        assert not hasattr(thread, '_finish_work')

def test_stop_after_initialization(thread):
    thread.start()
    with patch.object(thread, 'unblock'):
        thread.stop()
        assert thread.unblock.call_args_list == [call()]
        assert thread._finish_work is True


def test_unblock_unblocks(thread):
    thread.start()
    thread.unblock()
    assert thread._unblock_event.is_set()
    assert thread.is_alive

def test_unblock_autostarts(thread):
    assert not thread.is_alive
    thread.unblock()
    assert thread.is_alive


@pytest.mark.asyncio
async def test_join_when_thread_is_not_alive_with_no_exception(thread):
    thread._thread = Mock(is_alive=Mock(return_value=False))
    await thread.join()

@pytest.mark.asyncio
async def test_join_when_thread_is_not_alive_with_exception(thread):
    thread._thread = Mock(is_alive=Mock(return_value=False))
    thread._unhandled_exception = ValueError('Foo')
    for _ in range(3):
        with pytest.raises(ValueError, match=r'^Foo$'):
            await thread.join()

@pytest.mark.asyncio
async def test_join_joins_thread(thread):
    thread.start()
    assert thread.is_alive
    asyncio.get_event_loop().call_soon(thread.stop)
    await thread.join()
    assert not thread.is_alive


@pytest.mark.asyncio
async def test_initialize_raises_exception():
    class BarThread(FooThread):
        def initialize(self):
            raise TypeError('asdf')

    thread = BarThread()
    thread.start()
    with pytest.raises(TypeError, match=r'^asdf$'):
        await thread.join()
    assert not thread.is_alive


@pytest.mark.asyncio
async def test_work_raises_exception():
    class BarThread(FooThread):
        def work(self):
            raise TypeError('asdf')

    thread = BarThread()
    thread.start()
    thread.unblock()
    with pytest.raises(TypeError, match=r'^asdf$'):
        await thread.join()
    assert not thread.is_alive


@pytest.mark.asyncio
async def test_terminate_raises_exception():
    class BarThread(FooThread):
        def terminate(self):
            raise TypeError('asdf')

    thread = BarThread()
    thread.start()
    thread.stop()
    with pytest.raises(TypeError, match=r'^asdf$'):
        await thread.join()
    assert not thread.is_alive


@pytest.mark.asyncio
async def test_run_calls_user_methods_in_correct_order(thread):
    cbs = Mock()
    thread.initialize = cbs.initialize
    thread.work = cbs.work
    thread.work.side_effect = thread.stop
    thread.terminate = cbs.terminate
    thread.start()
    thread.unblock()
    await thread.join()
    assert cbs.mock_calls == [
        call.initialize(),
        call.work(),
        call.terminate(),
    ]

@pytest.mark.asyncio
async def test_run_calls_work_again_if_it_returns_True(thread):
    class BarThread(FooThread):
        counter = 0

        def work(self):
            self.counter += 1
            if self.counter < 5:
                return True   # Call me again
            else:
                self.stop()
                return False  # Do not call me again

    thread = BarThread()
    thread.start()
    thread.unblock()
    await thread.join()
    assert thread.counter == 5
