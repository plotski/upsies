"""
Background workers to keep the UI responsive
"""

import asyncio
import enum
import functools
import multiprocessing
import pickle

from .. import errors

import logging  # isort:skip
_log = logging.getLogger(__name__)


class MsgType(enum.Enum):
    """
    Enum that specifies the type of an IPC message (info, error, etc)
    """
    init = 'init'
    info = 'info'
    error = 'error'
    result = 'result'
    terminate = 'terminate'


class DaemonProcess:
    """
    :class:`multiprocessing.Process` abstraction with IPC

    Intended to offload heavy work (e.g. torrent creation) onto a different
    process. (Threads can still make the UI unresponsive because of the
    `GIL <https://wiki.python.org/moin/GlobalInterpreterLock>`_.)
    """

    def __init__(self, target, name=None, args=(), kwargs={},
                 init_callback=None, info_callback=None, error_callback=None,
                 result_callback=None, finished_callback=None):
        self._target = target
        self._name = name
        self._target_args = args
        self._target_kwargs = kwargs
        self._init_callback = init_callback
        self._info_callback = info_callback
        self._error_callback = error_callback
        self._result_callback = result_callback
        self._finished_callback = finished_callback

        self._ctx = multiprocessing.get_context('spawn')
        self._write_queue = self._ctx.Queue()
        self._read_queue = self._ctx.Queue()
        self._process = None
        self._read_queue_reader_task = None
        self._exception = None
        self._loop = asyncio.get_event_loop()

    def start(self):
        """Start the process"""
        _log.debug('Starting process: %r', self._target)
        target_wrapped = functools.partial(
            _target_process_wrapper,
            self._target,
            self._read_queue,
            self._write_queue,
        )
        self._process = self._ctx.Process(
            name=self._name,
            target=target_wrapped,
            args=self._make_args_picklable(self._target_args),
            kwargs=self._make_kwargs_picklable(self._target_kwargs),
        )
        self._process.start()
        self._read_queue_reader_task = self._loop.create_task(self._read_queue_reader())
        self._read_queue_reader_task.add_done_callback(self._handle_read_queue_reader_task_done)

    def _make_args_picklable(self, args):
        return tuple(self._get_picklable_value(arg) for arg in args)

    def _make_kwargs_picklable(self, kwargs):
        return {self._get_picklable_value(k): self._get_picklable_value(v)
                for k, v in kwargs.items()}

    def _get_picklable_value(self, value):
        # Try to pickle `value`. If it fails, try to instantiate `value` as one
        # of it's parent classes. Ignore first class (which is identical to
        # type(value)) and the last class, which should always be (`object`).
        types = type(value).mro()[1:-1]
        while True:
            try:
                pickle.dumps(value)
            # Python 3.9.1: This raises AttributeError, but the docs don't mention it.
            except Exception:
                if types:
                    value = types.pop(0)(value)
                else:
                    raise
            else:
                return value

    async def _read_queue_reader(self):
        while True:
            typ, msg = await self._loop.run_in_executor(None, self._read_queue.get)
            if typ is MsgType.init:
                if self._init_callback:
                    self._init_callback(msg)
            elif typ is MsgType.info:
                if self._info_callback:
                    self._info_callback(msg)
            elif typ is MsgType.error:
                if isinstance(msg, tuple):
                    exception, traceback = msg
                    raise errors.SubprocessError(exception, traceback)
                elif isinstance(msg, BaseException):
                    raise msg
                else:
                    if self._error_callback:
                        self._error_callback(msg)
            elif typ is MsgType.result:
                if self._result_callback:
                    self._result_callback(msg)
                break
            elif typ is MsgType.terminate:
                break
            else:
                raise RuntimeError(f'Unknown message type: {typ!r}')

    def _handle_read_queue_reader_task_done(self, task):
        # Catch exceptions from _read_queue_reader()
        try:
            task.result()
        except BaseException as e:
            _log.debug('Caught _read_queue_reader() exception: %r', e)
            self._exception = e
            if self._error_callback:
                self._error_callback(e)
            else:
                raise self._exception
        finally:
            if self._finished_callback:
                try:
                    self._finished_callback()
                except BaseException as e:
                    self._exception = e
                    if self._error_callback:
                        self._error_callback(e)
                    raise self._exception

    def stop(self):
        """Stop the process"""
        if self.is_alive:
            self._write_queue.put((MsgType.terminate, None))

    @property
    def is_alive(self):
        """Whether :meth:`start` was called and the process has not finished yet"""
        if self._process:
            return self._process.is_alive()
        else:
            return False

    @property
    def exception(self):
        """Exception from `target` or callback, `None` if no exception was raised"""
        task = self._read_queue_reader_task
        if task and task.done() and task.exception():
            return task.exception()
        else:
            return self._exception

    async def join(self):
        """Block asynchronously until the process exits"""
        if self._process:
            _log.debug('Joining process: %r', self._process)
            await self._loop.run_in_executor(None, self._process.join)
            self._process = None

        if self._read_queue_reader_task:
            if not self._read_queue_reader_task.done():
                # Unblock self._read_queue()
                self._read_queue.put((MsgType.terminate, None))
                await self._read_queue_reader_task
            exc = self.exception
            if exc:
                raise exc


def _target_process_wrapper(target, write_queue, read_queue, *args, **kwargs):
    try:
        target(write_queue, read_queue, *args, **kwargs)
    except BaseException as e:
        # Because the traceback is not picklable, preserve it as a string before
        # sending it over the Queue
        import traceback
        traceback = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        write_queue.put((MsgType.error, (e, traceback)))
    finally:
        write_queue.put((MsgType.terminate, None))
