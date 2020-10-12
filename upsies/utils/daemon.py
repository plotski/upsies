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
            self._finish_work = False
            self._unhandled_exception = None
            self._unblock_event = threading.Event()
            self._thread = threading.Thread(target=self._run,
                                            daemon=True,
                                            name=type(self).__name__)
            self._thread.start()
            _log.debug('Started thread: %r', self._thread)

    def stop(self):
        """Stop the thread"""
        if self.is_alive:
            _log.debug('Stopping thread: %r', self._thread)
            self._finish_work = True
            self.unblock()

    def initialize(self):
        """Do some work once inside the thread before it :meth:`work` is called"""
        pass

    @abc.abstractmethod
    def work(self):
        """
        A call for this method is scheduled every time :meth:`unblock` is called or
        when this method returns `True` or any other truthy value.
        """
        pass

    def terminate(self):
        """Do some work once inside the thread before it terminates"""
        pass

    def unblock(self):
        """Tell the background worker thread that there is work to do"""
        if not self.is_alive:
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
            self.initialize()
            while True:
                self._unblock_event.wait()
                if self._finish_work:
                    break
                call_again = self.work()
                if not call_again:
                    self._unblock_event.clear()
                # In case work() called stop()
                if self._finish_work:
                    break
            self.terminate()
        except BaseException as e:
            _log.debug('Reporting exception: %r', e)
            self._unhandled_exception = e
        finally:
            _log.debug('Finished: %r', self)


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
        _log.debug('Read output task: %r', self._read_output_task)

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
