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
    interface responsive.

    To raise any exceptions from the thread, :meth:`stop` and :meth:`join`
    should be called when the thread is no longer needed.

    :meth:`work` must be implemented by the subclass. It is called every time
    :meth:`unblock` is called or if it returns `True`.
    """

    def start(self):
        """Start the thread"""
        self._running = True
        self._unhandled_exception = None
        self._unblock_event = threading.Event()
        self._thread = threading.Thread(target=self._run,
                                        daemon=True,
                                        name=type(self).__name__)
        self._thread.start()
        _log.debug('Started thread: %r', self._thread)

    def stop(self):
        """Stop the thread"""
        _log.debug('Stopping %r', self)
        self._running = False
        self.unblock()

    def unblock(self):
        """Tell the background worker thread that there is work to do"""
        if hasattr(self, '_unblock_event'):
            self._unblock_event.set()
        else:
            raise RuntimeError(f'Not started yet: {self!r}')

    def initialize(self):
        """Do some background work once after :meth:`start` is called"""
        pass

    def terminate(self):
        """Do some background work once before the thread terminates"""
        pass

    @property
    def is_alive(self):
        """Whether :meth:`start` was called and the thread has not terminated yet"""
        if hasattr(self, '_thread'):
            return self._thread.is_alive()
        else:
            return False

    async def join(self, timeout=None):
        """Block asynchronously until the thread exits"""
        if hasattr(self, '_unblock_event'):
            # We want to wait asyncronously for _run() to finish, but asyncio.Event
            # is not thread-safe and threading.Event.wait() is synchronous. This
            # uses a new thread to allow us to await threading.Event().wait().
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, functools.partial(self._thread.join, timeout))
            if self._unhandled_exception:
                raise self._unhandled_exception
        else:
            raise RuntimeError(f'Not started yet: {self!r}')

    @property
    def running(self):
        """Whether :meth:`work` is going to be called again"""
        return getattr(self, '_running', False)

    @abc.abstractmethod
    def work(self):
        """Do some work in the background"""
        pass

    def _run(self):
        try:
            self.initialize()
            while True:
                self._unblock_event.wait()
                if not self._running:
                    break
                if not self.work():
                    self._unblock_event.clear()
                # In case work() called stop()
                if not self._running:
                    break
            self.terminate()
        except Exception as e:
            _log.debug('Reporting exception: %r', e)
            self._unhandled_exception = e
            self.stop()
        finally:
            _log.debug('Finished: %r', self)


class DaemonProcess:
    """
    Background worker process

    Intended to offload heavy jobs (e.g. torrent file creation) on a different
    CPU core to keep the rest of the application smooth.
    """

    INIT = 'init'
    INFO = 'info'
    ERROR = 'error'
    RESULT = 'result'
    _TERMINATED = 'terminated'

    def __init__(self, target, args=(), kwargs={},
                 init_callback=None, info_callback=None,
                 error_callback=None, finished_callback=None):
        self._target = target
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
            target=target_wrapped,
            args=self._target_args,
            kwargs=self._target_kwargs,
        )
        self._process.start()
        self._read_output_task = self._loop.create_task(self._read_output())
        self._read_output_task.add_done_callback(lambda task: task.result())
        _log.debug('Read output task: %r', self._read_output_task)

    async def _read_output(self):
        while self.is_alive:
            typ, msg = await self._loop.run_in_executor(None, self._output_queue.get)
            if typ == self.INIT:
                if self._init_callback:
                    self._init_callback(msg)
            elif typ == self.INFO:
                if self._info_callback:
                    self._info_callback(msg)
            elif typ == self.ERROR:
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
        if self._process is not None:
            self._process.terminate()

    @property
    def is_alive(self):
        """Whether :meth:`start` was called and the process has not finished yet"""
        if self._process is not None:
            return self._process.is_alive()
        else:
            return False

    async def join(self):
        """Block asynchronously until the process exits"""
        await self._loop.run_in_executor(None, self._process.join)
        _log.debug('Process finished: %r', self._process)
        # Unblock _read_output()
        if not self._read_output_task.done():
            self._output_queue.put((self._TERMINATED, None))
            await self._read_output_task


def _target_process_wrapper(target, output_queue, input_queue, *args, **kwargs):
    try:
        target(output_queue, input_queue, *args, **kwargs)
    except BaseException as e:
        import traceback
        msg = ''.join(traceback.format_exception(type(e), e, e.__traceback__)).strip()
        output_queue.put((DaemonProcess.ERROR, msg))
