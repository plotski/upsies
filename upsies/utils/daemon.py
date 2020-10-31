import asyncio
import functools
import multiprocessing

from .. import errors

import logging  # isort:skip
_log = logging.getLogger(__name__)


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
                if isinstance(msg, tuple):
                    exception, traceback = msg
                    raise errors.SubprocessError(exception, traceback)
                elif isinstance(msg, BaseException):
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
    except BaseException as e:
        # Because the traceback is not picklable, preserve it as a string before
        # sending it over the Queue
        import traceback
        traceback = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        output_queue.put((DaemonProcess.ERROR, (e, traceback)))
    finally:
        output_queue.put((DaemonProcess._TERMINATED, None))
