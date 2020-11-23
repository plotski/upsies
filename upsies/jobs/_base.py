import abc
import asyncio
import collections
import json
import os

from ..utils import cache, signal

import logging  # isort:skip
_log = logging.getLogger(__name__)


class JobBase(abc.ABC):
    """
    Base class for all jobs

    :param str homedir: Directory that is used to store files and cache output
    :param str ignore_cache: Whether cached output and previously created files
        should not be re-used
    :param bool hidden: Whether to hide the job's output in the UI

    Any additional keyword arguments are passed on to :meth:`initialize`.

    Exceptions
    ==========

    Methods and properties of jobs should not raise any exceptions. Exceptions
    should be passed to :meth:`error` or :meth:`exception` and the job should
    :meth:`finish` immediately with an :attr:`exit_code` > 0.

    Arguments should be validated before creating a job to fail early when
    sibling jobs haven't started doing work that has to be cancelled in case of
    error.
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

    @property
    def kwargs(self):
        """Job-specific keyword arguments as a dictionary"""
        return self._kwargs

    @property
    def signal(self):
        """
        :class:`~signal.Signal` instance

        The following signals are added by the base class. Subclasses can add
        their own signals.

        `finished` is emitted when :meth:`finish` is called or when output is
        read from cache. Registered callbacks get no arguments.

        `output` is emitted when :meth:`send` is called or when output is read
        from cache. Registered callbacks get the value passed to :meth:`send` as
        a positional argument.

        `error` is emitted when :meth:`error` is called. Registered callbacks
        get the value passed to :meth:`error` as a positional argument.
        """
        return self._signal

    def __init__(self, *, homedir, ignore_cache, hidden=False, **kwargs):
        self._homedir = str(homedir)
        self._ignore_cache = bool(ignore_cache)
        self._hidden = bool(hidden)
        self._is_started = False
        self._exception = None
        self._errors = []
        self._output = []
        self._signal = signal.Signal('output', 'error', 'finished')
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

        If there is cached output available, load it, emit `finished` signal and
        finally call :meth:`finish`. Otherwise, call :meth:`execute`.

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
                self.signal.emit('output', output)
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
            self.signal.emit('finished')
            self._write_output_cache()

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

    @property
    def info(self):
        """
        Additional information that is only displayed in the UI and not part of the
        job's result
        """
        return ''

    def send(self, output):
        """Append `output` to :attr:`output` and emit `output` signal"""
        if not self.is_finished:
            if output:
                output_str = str(output)
                self._output.append(output_str)
                self.signal.emit('output', output_str)

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

    def clear_errors(self):
        """Empty :attr:`errors`"""
        if not self.is_finished:
            self._errors.clear()

    def error(self, error, finish=False):
        """
        Append `error` to :attr:`errors` and emit `error` signal

        :param bool finish: Whether to call :meth:`finish` after handling
            `error`
        """
        if not self.is_finished:
            self._errors.append(error)
            self.signal.emit('error', error)
            if finish:
                self.finish()

    def exception(self, exception):
        """
        Set exception to raise in :meth:`wait` and call :meth:`finish`

        .. warning:: Setting an exception means you want to throw a traceback in
                     the user's face, which is likely not a good idea.

        :param Exception exception: Exception instance
        """
        if not self.is_finished:
            import traceback
            tb = ''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__))
            _log.debug('Exception in %s: %s', self.name, tb)
            self._exception = exception
            self.finish()

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
        """
        path = os.path.join(self.homedir, '.output')
        if not os.path.exists(path):
            os.mkdir(path)
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
            def string_value(value):
                if isinstance(value, collections.abc.Sequence) and not isinstance(value, str):
                    return ','.join((string_value(v) for v in value))

                elif isinstance(value, collections.abc.Mapping):
                    return ','.join((f'{k}={string_value(v)}' for k, v in value.items()))

                # Use same cache file for absolute and relative paths
                if isinstance(value, (str, os.PathLike)) and os.path.exists(value):
                    return str(os.path.realpath(value))

                return str(value)

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
