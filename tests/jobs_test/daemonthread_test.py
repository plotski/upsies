import threading

import pytest

from upsies.jobs._common import DaemonThread


class FooThread(DaemonThread):
    def work(self):
        pass


@pytest.mark.parametrize('method', DaemonThread.__abstractmethods__)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in DaemonThread.__abstractmethods__}
    del attrs[method]
    cls = type('Foo', (DaemonThread,), attrs)
    # Python 3.9 changed "methods" to "method"
    exp_msg = rf"^Can't instantiate abstract class Foo with abstract methods? {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


@pytest.mark.asyncio
async def test_is_alive():
    thread = FooThread()
    assert thread.is_alive is False
    thread.start()
    assert thread.is_alive is True
    thread.stop()
    await thread.join(timeout=1)
    assert thread.is_alive is False


@pytest.mark.asyncio
async def test_initialize_raises_exception():
    class BarThread(FooThread):
        def initialize(self):
            raise TypeError('asdf')

    thread = BarThread()
    thread.start()
    with pytest.raises(TypeError, match=r'^asdf$'):
        await thread.join(timeout=1)


@pytest.mark.asyncio
async def test_work_raises_exception():
    class BarThread(FooThread):
        error_sent = threading.Event()

        def work(self):
            self.error_sent.set()
            raise TypeError('asdf')

    thread = BarThread()
    thread.start()
    thread.unblock()
    thread.error_sent.wait()
    with pytest.raises(TypeError, match=r'^asdf$'):
        await thread.join(timeout=1)


@pytest.mark.asyncio
async def test_terminate_raises_exception():
    class BarThread(FooThread):
        def terminate(self):
            raise TypeError('asdf')

    thread = BarThread()
    thread.start()
    thread.stop()
    with pytest.raises(TypeError, match=r'^asdf$'):
        await thread.join(timeout=1)


@pytest.mark.asyncio
async def test_stop_terminates_endless_work():
    class BarThread(FooThread):
        counter = 0

        def initialize(self):
            self.unblock()

        def work(self):
            while self.running:
                self.counter += 1

    thread = BarThread()
    thread.start()
    thread.stop()
    await thread.join(timeout=5)
    assert thread.counter > 0
    assert thread.is_alive is False


@pytest.mark.asyncio
async def test_work_method_can_unblock_and_stop():
    class BarThread(FooThread):
        counter = 0

        def initialize(self):
            self.unblock()

        def work(self):
            self.counter += 1
            if self.counter < 5:
                return 'Call me again!'  # Anything truthy
            else:
                self.stop()

    thread = BarThread()
    thread.start()
    await thread.join(timeout=1)
    assert thread.counter == 5
    assert thread.is_alive is False


def test_calling_unblock_before_start():
    thread = FooThread()
    with pytest.raises(RuntimeError, match=rf'^Not started yet: {thread!r}'):
        thread.unblock()


@pytest.mark.asyncio
async def test_calling_join_before_start():
    thread = FooThread()
    with pytest.raises(RuntimeError, match=rf'^Not started yet: {thread!r}'):
        await thread.join()
