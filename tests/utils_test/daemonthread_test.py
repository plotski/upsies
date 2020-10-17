import asyncio
import threading
from unittest.mock import Mock, call, patch

import pytest

from upsies.utils.daemon import DaemonThread


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


class FooThread(DaemonThread):
    async def work(self):
        pass

@pytest.fixture
def thread():
    thread = FooThread()
    yield thread
    # Raise any exceptions from thread target unless it was stopped by the test
    if thread.is_alive:
        thread.stop()
        asyncio.get_event_loop().run_until_complete(thread.join())


@pytest.mark.parametrize('method', DaemonThread.__abstractmethods__)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in DaemonThread.__abstractmethods__}
    del attrs[method]
    cls = type('Foo', (DaemonThread,), attrs)
    # Python 3.9 changed "methods" to "method"
    exp_msg = rf"^Can't instantiate abstract class Foo with abstract methods? {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def test_is_alive(thread):
    assert thread.is_alive is False
    thread.start()
    assert thread.is_alive is True


@patch('upsies.utils.daemon.threading.Thread')
def test_start_initializes(Thread_mock):
    thread = FooThread()
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

def test_start_can_be_called_multiple_times(thread):
    assert thread.is_alive is False
    thread.start()
    assert thread.is_alive is True
    thread.start()
    assert thread.is_alive is True

def test_start_can_be_called_from_multiple_threads(thread):
    class ThreadStarter:
        def __init__(self, start_threads_count):
            self.exceptions = []
            all_starter_threads_started = threading.Event()
            threads = []

            def start_test_thread(i):
                # Wait until all starter threads are running
                all_starter_threads_started.wait()
                # Exceptions are ignored unless we stash them
                try:
                    thread.start()
                except BaseException as e:
                    self.exceptions.append(e)

            # Initiate starter threads
            for i in range(start_threads_count):
                t = threading.Thread(target=start_test_thread, args=(i,))
                t.start()
                threads.append(t)

            # Tell all starter threads to call thread.start() at the same time
            all_starter_threads_started.set()

            # Wait for starter threads to finish
            for t in threads:
                t.join()

    assert thread.is_alive is False
    ts = ThreadStarter(10)
    assert thread.is_alive is True
    assert ts.exceptions == []

@pytest.mark.asyncio
async def test_start_after_stop(thread):
    thread.start()
    assert thread.is_alive
    thread.stop()
    await thread.join()
    assert not thread.is_alive
    with pytest.raises(RuntimeError, match=r'threads can only be started once'):
        thread.start()
    assert not thread.is_alive


def test_stop_before_start(thread):
    with patch.object(thread, 'unblock'):
        thread.stop()
        assert thread.unblock.call_args_list == []
        assert thread._finish_work is False

def test_stop_after_start(thread):
    thread.start()
    with patch.object(thread, 'unblock'):
        thread.stop()
        assert thread.unblock.call_args_list == [call()]
        assert thread._finish_work is True


def test_unblock_before_start(thread):
    thread._unblock_event.clear()
    with patch.object(thread, 'start'):
        thread.unblock()
        assert thread.start.call_args_list == [call()]
        assert thread._unblock_event.is_set()

def test_unblock_after_start(thread):
    thread.start()
    thread._unblock_event.clear()
    with patch.object(thread, 'start'):
        thread.unblock()
        assert thread.start.call_args_list == []
        assert thread._unblock_event.is_set()

@pytest.mark.asyncio
async def test_unblock_after_stop(thread):
    thread.start()
    assert thread.is_alive
    thread.stop()
    await thread.join()
    assert not thread.is_alive
    thread._unblock_event.clear()
    with patch.object(thread, 'start'):
        thread.unblock()
        assert thread.start.call_args_list == []
        assert thread._unblock_event.is_set()


@pytest.mark.asyncio
async def test_join_when_thread_is_not_alive_with_no_exception(thread):
    thread._thread = Mock(is_alive=Mock(return_value=False))
    await thread.join()

@pytest.mark.asyncio
async def test_join_when_thread_is_not_alive_with_exception(thread):
    thread._thread = Mock(is_alive=Mock(return_value=False))
    thread._unhandled_exception = ValueError('Foo')
    for _ in range(3):
        with pytest.raises(ValueError):
            await thread.join()

@pytest.mark.asyncio
async def test_join_joins_thread(thread):
    thread.start()
    assert thread.is_alive
    thread.stop()
    await thread.join()
    assert not thread.is_alive


def test_cancel_work_with_no_running_work_task(thread):
    assert not thread.is_alive
    thread.cancel_work()
    assert not thread.is_alive

@pytest.mark.asyncio
async def test_cancel_work_with_running_work_task(thread):
    thread._work_task = Mock(done=Mock(return_value=False))
    with patch.object(thread, '_loop'):
        thread.cancel_work()
        assert thread._work_task.done.call_args_list == [call()]
        assert thread._loop.call_soon_threadsafe.call_args_list == [call(thread._work_task.cancel)]

@pytest.mark.asyncio
async def test_cancel_work_with_done_work_task(thread):
    thread._work_task = Mock(done=Mock(return_value=True))
    with patch.object(thread, '_loop'):
        thread.cancel_work()
        assert thread._work_task.done.call_args_list == [call()]
        assert thread._loop.call_soon_threadsafe.call_args_list == []


@pytest.mark.asyncio
async def test_run_calls_user_methods_in_correct_order(thread):
    cbs = AsyncMock()
    thread.initialize = cbs.initialize
    thread.work = cbs.work
    thread.work.side_effect = thread.stop  # So that join() returns
    thread.terminate = cbs.terminate
    thread.start()
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

        async def work(self):
            self.counter += 1
            if self.counter < 5:
                return True   # Call me again
            else:
                self.stop()
                return False  # Do not call me again

    thread = BarThread()
    thread.start()
    await thread.join()
    assert thread.counter == 5


@pytest.mark.asyncio
async def test_initialize_raises_exception():
    class BarThread(FooThread):
        async def initialize(self):
            raise TypeError('asdf')

    thread = BarThread()
    thread.start()
    with pytest.raises(TypeError, match=r'^asdf$'):
        await thread.join()
    assert not thread.is_alive


@pytest.mark.asyncio
async def test_work_raises_exception():
    class BarThread(FooThread):
        async def work(self):
            raise TypeError('asdf')

    thread = BarThread()
    thread.start()
    with pytest.raises(TypeError, match=r'^asdf$'):
        await thread.join()
    assert not thread.is_alive


@pytest.mark.asyncio
async def test_terminate_raises_exception():
    class BarThread(FooThread):
        async def terminate(self):
            raise TypeError('asdf')

    thread = BarThread()
    thread.start()
    thread.stop()
    with pytest.raises(TypeError, match=r'^asdf$'):
        await thread.join()
    assert not thread.is_alive
