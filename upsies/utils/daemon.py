import abc
import asyncio
import functools
import multiprocessing
import threading

import logging  # isort:skip
_log = logging.getLogger(__name__)


class DaemonThread(abc.ABC):
    """
    Base class for background worker thread

    Intended for blocking stuff (e.g. network requests) to keep the user
    interface responsive. (Asynchronous calls can still block the main thread.)

    To raise any exceptions from the thread, :meth:`stop` and :meth:`join`
    should be called when the thread is no longer needed.

    :meth:`work` must be implemented by the subclass. It is called every time
    :meth:`unblock` is called or if :meth:`work` returns `True`.
    """

    asyncio_debug = False
    """Enable debugging messages for the internal asyncio loop"""

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._loop.set_debug(self.asyncio_debug)
        self._finish_work = False
        self._unhandled_exception = None
        self._unblock_event = threading.Event()
        self._thread = threading.Thread(target=self._run,
                                        daemon=True,
                                        name=type(self).__name__)

    async def initialize(self):
        """Do some work once inside the thread before :meth:`work` is called"""
        pass

    @abc.abstractmethod
    async def work(self):
        """
        Coroutine function that does one task an returns

        A call for this method is scheduled every time :meth:`unblock` is called or
        when this method returns `True` or any other truthy value.
        """
        pass

    async def terminate(self):
        """Do some work once inside the thread before it terminates"""
        pass

    @property
    def is_alive(self):
        """Whether :meth:`start` was called and the thread has not terminated yet"""
        if hasattr(self, '_thread'):
            return self._thread.is_alive()
        else:
            return False

    def start(self):
        """Start the thread"""
        if not self.is_alive:
            self._thread.start()
            _log.debug('Started thread: %r', self._thread)
            self._unblock_event.set()

    def stop(self):
        """Stop the thread"""
        if self.is_alive:
            _log.debug('Stopping thread: %r', self._thread)
            self._finish_work = True
            self.unblock()

    def unblock(self):
        """Tell the background worker thread that there is work to do"""
        if not self.is_alive and not self._finish_work:
            self.start()
        self._unblock_event.set()

    async def join(self):
        """Block asynchronously until the thread exits"""
        if self.is_alive:
            # Use another thread to join self._thread asynchronously
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._thread.join)
        if getattr(self, '_unhandled_exception', None):
            raise self._unhandled_exception

    def _run(self):
        try:
            self._run_coro(self.initialize())
            while True:
                # Wait for unblock() call
                self._unblock_event.wait()

                # Don't call work() if stop() was called
                if self._finish_work:
                    break

                call_again = self._run_coro(self._work())
                if not call_again:
                    self._unblock_event.clear()

                # Don't wait for unblock() again if stop() was called
                if self._finish_work:
                    break
            self._run_coro(self.terminate())
        except Exception as e:
            _log.debug('Reporting exception: %r', e)
            self._unhandled_exception = e
        finally:
            _log.debug('_run() finished: %r', self._thread)

    def _run_coro(self, coro):
        if self._loop.is_running():
            self._stop_loop()
        return self._loop.run_until_complete(coro)

    async def _work(self):
        try:
            return await self.work()
        except asyncio.CancelledError:
            _log.debug('%s was cancelled', type(self).__name__)
            # Call work() again
            return True
        except RuntimeError as e:
            # Ugly hack; see FIXME in _stop_loop()
            if str(e) == 'Event loop stopped before Future completed.':
                _log.debug('Caught ugly hack.')
            else:
                raise

    def _stop_loop(self):
        # FIXME: We want self._task to stop immediately, because
        #        1) aborting quickly is good UX
        #        2) when run_until_complete() is called with the new task
        #           and the previous task hasn't finished yet, we get a
        #           RuntimeError.
        #
        #        Canceling self._task doesn't necessarily cancel it because
        #        its coroutine function might use a ThreadPoolExecutor to
        #        fake async behaviour. Those tasks can't be cancelled (at
        #        least not easily): https://stackoverflow.com/a/52938384
        #
        #        Stopping the loop "kills" self._task immediately and raises
        #        RuntimeError('Event loop stopped before Future completed.')
        #        in work().
        #
        #        This is horrible and will probably explode in someone's
        #        face. Sorry.
        #
        #        If, at some point, work() doesn't use
        #        Thread/ProcessPoolExecutors, self._task.cancel() should be
        #        better.
        self._loop.stop()
        _log.debug('Cancelled %r', type(self).__name__)


class DaemonProcess:
    """
    Background worker process

    Intended to offload heavy work (e.g. torrent creation) onto a different
    process. (Threads can still make the UI unresponsive because of the GIL.)
    """

    INIT = 'init'
    INFO = 'info'
    ERROR = 'error'
    RESULT = 'result'
    _TERMINATED = 'terminated'

    def __init__(self, target, name=None, args=(), kwargs={},
                 init_callback=None, info_callback=None,
                 error_callback=None, finished_callback=None):
        self._target = target
        self._name = name
        self._target_args = args
        self._target_kwargs = kwargs
        self._init_callback = init_callback
        self._info_callback = info_callback
        self._error_callback = error_callback
        self._finished_callback = finished_callback

        self._ctx = multiprocessing.get_context('spawn')
        self._input_queue = self._ctx.Queue()
        self._output_queue = self._ctx.Queue()
        self._process = None
        self._read_output_task = None
        self._loop = asyncio.get_event_loop()

    def start(self):
        """Start the process"""
        _log.debug('Starting process: %r', self._target)
        target_wrapped = functools.partial(
            _target_process_wrapper,
            self._target,
            self._output_queue,
            self._input_queue,
        )
        self._process = self._ctx.Process(
            name=self._name,
            target=target_wrapped,
            args=self._target_args,
            kwargs=self._target_kwargs,
        )
        self._process.start()
        self._read_output_task = self._loop.create_task(self._read_output())

    async def _read_output(self):
        while True:
            typ, msg = await self._loop.run_in_executor(None, self._output_queue.get)
            if typ == self.INIT:
                if self._init_callback:
                    self._init_callback(msg)
            elif typ == self.INFO:
                if self._info_callback:
                    self._info_callback(msg)
            elif typ == self.ERROR:
                if isinstance(msg, Exception):
                    raise msg
                else:
                    if self._error_callback:
                        self._error_callback(msg)
            elif typ == self.RESULT:
                if self._finished_callback:
                    self._finished_callback(msg)
                break
            elif typ == self._TERMINATED:
                if self._finished_callback:
                    self._finished_callback()
                break
            else:
                raise RuntimeError(f'Unknown message type: {typ!r}')

    def stop(self):
        """Stop the process"""
        if self._process:
            # TODO: Don't use terminate(), see "Avoid terminating processes":
            #       https://docs.python.org/3/library/multiprocessing.html
            self._process.terminate()
            self._output_queue.put((DaemonProcess._TERMINATED, None))

    @property
    def is_alive(self):
        """Whether :meth:`start` was called and the process has not finished yet"""
        if self._process:
            return self._process.is_alive()
        else:
            return False

    async def join(self):
        """Block asynchronously until the process exits"""
        if self._process:
            _log.debug('Waiting for process: %r', self._process)
            await self._loop.run_in_executor(None, self._process.join)
            _log.debug('Process finished: %r', self._process)
            self._process = None

        if self._read_output_task:
            if not self._read_output_task.done():
                self._output_queue.put((self._TERMINATED, None))
                await self._read_output_task
            exc = self._read_output_task.exception()
            if exc:
                raise exc


def _target_process_wrapper(target, output_queue, input_queue, *args, **kwargs):
    try:
        target(output_queue, input_queue, *args, **kwargs)
    except Exception as e:
        # Because tracebacks are not picklable, format the exception in the
        # child process before we send it to the parent.
        output_queue.put((DaemonProcess.ERROR, _PickledException(e)))
    finally:
        output_queue.put((DaemonProcess._TERMINATED, None))

class _PickledException(Exception):
    def __init__(self, exc):
        import traceback
        self._formatted = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    def __str__(self):
        return self._formatted
