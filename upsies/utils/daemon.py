"""
Background workers to keep the UI responsive
"""

import asyncio
import enum
import functools
import multiprocessing

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
            args=self._target_args,
            kwargs=self._target_kwargs,
        )
        self._process.start()
        self._read_queue_reader_task = self._loop.create_task(self._read_queue_reader())

    async def _read_queue_reader(self):
        try:
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
                    if self._finished_callback:
                        self._finished_callback(msg)
                    break
                elif typ is MsgType.terminate:
                    if self._finished_callback:
                        self._finished_callback()
                    break
                else:
                    raise RuntimeError(f'Unknown message type: {typ!r}')
        except BaseException as e:
            self._exception = e
            self._error_callback(e)

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
            exc = self._read_queue_reader_task.exception() or self._exception
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
