import abc
import asyncio
import json
import os

from .. import errors
from ..utils import cache

import logging  # isort:skip
_log = logging.getLogger(__name__)


class JobBase(abc.ABC):
    """
    Base class for all jobs

    :param str homedir: Directory that is used to store files
    :param str ignore_cache: Whether cached output and previously created files
        should not be re-used
    :param bool hidden: Whether to hide this job's output in the UI

    Any additional keyword arguments are passed on to :meth:`initialize`.
    """

    @property
    @abc.abstractmethod
    def name(self):
        """Internal name (e.g. for the cache file name)"""
        pass

    @property
    @abc.abstractmethod
    def label(self):
        """User-facing name"""
        pass

    @property
    def homedir(self):
        """
        Directory that is used to store files

        Cached output is stored in a subdirectory called ".output".
        """
        return self._homedir

    @property
    def ignore_cache(self):
        """Whether cached output and previously created files should not be re-used"""
        return self._ignore_cache

    @property
    def hidden(self):
        """Whether to hide this job's output in the UI"""
        return self._hidden

    def __init__(self, *, homedir, ignore_cache, hidden=False, **kwargs):
        self._homedir = str(homedir)
        self._ignore_cache = bool(ignore_cache)
        self._hidden = bool(hidden)
        self._is_started = False
        self._exception = None
        self._errors = []
        self._output = []
        self._output_callbacks = []
        self._error_callbacks = []
        self._finished_callbacks = []
        self._finished_event = asyncio.Event()
        self._kwargs = kwargs
        self.initialize(**kwargs)

    @abc.abstractmethod
    def initialize(self):
        """
        Called by :meth:`__init__` with additional keyword arguments

        This method should handle its arguments and return quickly.
        """
        pass

    @abc.abstractmethod
    def execute(self):
        """
        Do the job, e.g. prompt for user input or start background worker

        This method must not block.
        """
        pass

    def start(self):
        """
        Called by the main entry point when this job is executed

        If there is cached output available, load it, call any callbacks
        registered via :meth:`on_finished` and finally call :meth:`finish`.
        Otherwise, call :meth:`execute`.

        :raise RuntimeError: if this method is called multiple times or if
            reading from cache file fails unexpectedly
        """
        if self._is_started:
            raise RuntimeError('start() was already called')
        else:
            self._is_started = True

        try:
            self._read_output_cache()
        except Exception:
            self.finish()
            raise

        if self.output:
            _log.debug('Job was already done previously: %r', self)
            for output in self.output:
                for cb in self._output_callbacks:
                    cb(output)
            self.finish()
        else:
            _log.debug('Executing %r', self)
            self.execute()

    async def wait(self):
        """
        Wait for this job to finish

        This method returns when :meth:`finish` is called.

        :attr:`is_finished` is `False` before this method returns and `True`
        afterwards.

        Calling this method multiple times simultaneously must be safe.

        Subclass implementations of this method must call their parent's
        implementation.

        :raise: Any exceptions given to :meth:`exception`
        """
        await self._finished_event.wait()
        if self._exception is not None:
            raise self._exception

    def finish(self):
        """
        Cancel this job if it is not finished yet

        Calling this method unblocks any calls to :meth:`wait`.

        :attr:`is_finished` is `False` before this method returns and `True`
        afterwards.

        Subclass implementations of this method must call their parent's
        implementation.

        This method must not block.
        """
        if not self.is_finished:
            self._finished_event.set()
            for cb in self._finished_callbacks:
                cb(self)
            self._write_output_cache()

    def on_finished(self, callback):
        """
        Call `callback` when job is finished

        :param callable callback: Callable that takes an instance of this class
            as a positional argument

        `callback` is called when :meth:`finish` is called and when output is
        read from cache.
        """
        assert callable(callback)
        self._finished_callbacks.append(callback)

    @property
    def is_finished(self):
        """Whether :meth:`finish` was called"""
        return self._finished_event.is_set()

    @property
    def exit_code(self):
        """`0` if job was successful, `> 0` otherwise, None while job is not finished"""
        if self.is_finished:
            if not self.output or self.errors or self._exception:
                return 1
            else:
                return 0

    @property
    def output(self):
        """Result of this job as a sequence of strings"""
        return tuple(self._output)

    def send(self, output):
        """
        Append `output` to :attr:`output`

        :raise RuntimeError: if :meth:`finish` was called earlier
        """
        if not self.is_finished:
            if output:
                output_str = str(output)
                self._output.append(output_str)
                for cb in self._output_callbacks:
                    cb(output_str)
        else:
            raise RuntimeError('send() called on finished job')

    def on_output(self, callback):
        """
        Call `callback` with output

        :param callable callback: Callable that takes an instance of this class
            as a positional argument

        `callback` is called when :meth:`send` is called and when cached output
        is read (i.e. :meth:`executed` is never called).
        """
        assert callable(callback)
        self._output_callbacks.append(callback)

    def pipe_input(self, value):
        """
        Called by :class:`~utils.pipe.Pipe` on the receiving job for each output from sending
        job
        """
        raise NotImplementedError(f'pipe_input() is not implemented in {type(self).__name__}')

    def pipe_closed(self):
        """
        Called by :class:`~utils.pipe.Pipe` on the receiving job when the sending job is
        finished
        """
        raise NotImplementedError(f'pipe_closed() is not implemented in {type(self).__name__}')

    @property
    def errors(self):
        """Sequence of reported errors (strings or exceptions)"""
        return tuple(self._errors)

    def error(self, error):
        """
        Append `error` to :attr:`errors` and call error callbacks

        :raise RuntimeError: if :meth:`finish` was called earlier
        """
        if not self.is_finished:
            self._errors.append(error)
            for cb in self._error_callbacks:
                cb(error)
        else:
            raise RuntimeError('error() called on finished job')

    def on_error(self, callback):
        """
        Call `callback` with error

        :param callable callback: Callable that takes the argument given to
            :meth:`error`
        """
        assert callable(callback)
        self._error_callbacks.append(callback)

    def exception(self, exception):
        """
        Set exception to raise in :meth:`wait`

        :param Exception exception: Exception instance
        """
        if not self.is_finished:
            import traceback
            tb = ''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__))
            _log.debug('Exception in %s: %s', self.name, tb)
            self._exception = exception
            self.finish()
        else:
            raise RuntimeError('exception() called on finished job')

    @property
    def info(self):
        """
        Additional information that is only displayed in the UI and not part of the
        job's result
        """
        return ''

    def _write_output_cache(self):
        """
        Store :attr:`output` in :attr:`cache_file`

        The base class implementation stores output as JSON. Child classes may
        want to use other formats.

        :raise RuntimeError: if :attr:`output` is not JSON-encodable or
            :attr:`cache_file` is not writable
        """
        if self.output and self.exit_code == 0 and self.cache_file:
            try:
                output_string = json.dumps(self.output)
            except (ValueError, TypeError) as e:
                raise RuntimeError(f'Unable to serialize JSON: {self.output!r}: {e}')
            else:
                try:
                    with open(self.cache_file, 'w') as f:
                        f.write(output_string)
                        f.write('\n')
                except OSError as e:
                    if e.strerror:
                        raise RuntimeError(f'Unable to write cache {self.cache_file}: {e.strerror}')
                    else:
                        raise RuntimeError(f'Unable to write cache {self.cache_file}: {e}')

    def _read_output_cache(self):
        """
        Set :attr:`output` to data stored in :attr:`cache_file`

        :raise RuntimeError: if :attr:`cache_file` exists and is unreadable or
            unparsable
        """
        if not self._ignore_cache and self.cache_file and os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    content = f.read()
            except OSError as e:
                if e.strerror:
                    raise RuntimeError(f'Unable to read cache {self.cache_file}: {e.strerror}')
                else:
                    raise RuntimeError(f'Unable to read cache {self.cache_file}: {e}')
            else:
                try:
                    self._output = json.loads(content)
                except (ValueError, TypeError) as e:
                    raise RuntimeError(f'Unable to decode JSON: {content!r}: {e}')

    @cache.property
    def cache_directory(self):
        """
        Path to directory that stores cache files

        The directory is created if it doesn't exist.

        :raise PermissionError: if directory creation fails
        """
        path = os.path.join(self.homedir, '.output')
        if not os.path.exists(path):
            try:
                os.mkdir(path)
            except OSError as e:
                if getattr(e, 'strerror', None):
                    raise errors.PermissionError(f'{path}: {e.strerror}')
                else:
                    raise errors.PermissionError(f'{path}: Unable to create directory')
        return path

    @cache.property
    def cache_file(self):
        """
        File path in :attr:`cache_directory` to store cached :attr:`output` in

        It is important that the file name is unique for each output. By
        default, this is achieved by including the keyword arguments for
        :meth:`initialize`. See :attr:`ScreenshotsJob.cache_file` for a
        different implementation.

        If this property returns a falsy value, no cache file is read or
        written.
        """
        if self._kwargs:
            def string_value(v):
                v = str(v)
                # Use same cache file for absolute and relative paths
                if os.path.exists(v):
                    v = os.path.realpath(v)
                return v

            kwargs_str_max_len = 250 - len(self.name) - len('..json')
            kwargs_str = ','.join(f'{k}={string_value(v)}'
                                  for k, v in self._kwargs.items())
            if len(kwargs_str) > kwargs_str_max_len:
                kwargs_str = ''.join((
                    kwargs_str[:int(kwargs_str_max_len / 2 - 1)],
                    '…',
                    kwargs_str[-int(kwargs_str_max_len / 2 - 1):],
                ))
            filename = f'{self.name}.{kwargs_str}.json'
        else:
            filename = f'{self.name}.json'
        filename = filename.replace("/", "_")
        assert len(filename) < 250
        return os.path.join(self.cache_directory, filename)
