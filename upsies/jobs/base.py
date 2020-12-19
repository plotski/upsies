"""
Abstract base class for jobs
"""

import abc
import asyncio
import collections
import json
import os

from ..utils import cached_property, fs, signal

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

    If possible, arguments should be validated before creating a job to fail
    early when sibling jobs haven't started doing work that has to be cancelled
    in case of error.

    Methods and properties of jobs should not raise any expected exceptions.
    Exceptions should instead be passed to :meth:`error` (report message to
    user) or to :meth:`exception` (throw traceback at user), and the job should
    :meth:`finish` immediately with an :attr:`exit_code` `> 0`.
    """

    @property
    @abc.abstractmethod
    def name(self):
        """Internal name (e.g. for the cache file name)"""

    @property
    @abc.abstractmethod
    def label(self):
        """User-facing name"""

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
        :class:`~.signal.Signal` instance

        The following signals are added by the base class. Subclasses can add
        their own signals.

        ``finished``
            is emitted when :meth:`finish` is called or when output is read from
            cache. Registered callbacks get no arguments.

        ``output``
            is emitted when :meth:`send` is called or when output is read from
            cache. Registered callbacks get the value passed to :meth:`send` as
            a positional argument.

        ``error``
            is emitted when :meth:`error` is called. Registered callbacks get
            the value passed to :meth:`error` as a positional argument.
        """
        return self._signal

    def __init__(self, *, homedir='.', ignore_cache=False, hidden=False, **kwargs):
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

    def initialize(self):
        """
        Called by :meth:`__init__` with additional keyword arguments

        This method should handle its arguments and return quickly.
        """
        pass

    def execute(self):
        """
        Do the job, e.g. prompt for user input or start background worker

        This method must not block.
        """
        pass

    def start(self):
        """
        Called by the main entry point when this job is executed

        If there is cached output available, load it and call :meth:`finish`.
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
                self.signal.emit('output', output)
            self.finish()
        else:
            _log.debug('Executing %r', self)
            self.execute()

    async def wait(self):
        """
        Wait for this job to finish

        Subclasses that need to wait for I/O should override this method to
        `await` their coroutines before awaiting ``super().wait()``.

        This method must return when :meth:`finish` is called.

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
        Cancel this job if it is not finished yet and emit ``finished`` signal

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
        """Result of this job as an immutable sequence of strings"""
        return tuple(self._output)

    @property
    def info(self):
        """
        Additional information that is only displayed in the UI and not part of the
        job's result
        """
        return ''

    def send(self, output):
        """Append `output` to :attr:`output` and emit ``output`` signal"""
        if not self.is_finished:
            if output:
                output_str = str(output)
                self._output.append(output_str)
                self.signal.emit('output', output_str)

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
        Append `error` to :attr:`errors` and emit ``error`` signal

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
                     the user's face, which may not be a good idea.

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
        use other formats.

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

    @cached_property
    def cache_directory(self):
        """
        Path to directory that stores cache files

        The directory is created if it doesn't exist.
        """
        path = os.path.join(self.homedir, '.output')
        if not os.path.exists(path):
            os.mkdir(path)
        return path

    @cached_property
    def cache_file(self):
        """
        File path in :attr:`cache_directory` to store cached :attr:`output` in

        If this property returns `None`, cache is not read or written.
        """
        cache_id = self.cache_id
        if cache_id is None:
            return None
        elif cache_id == '':
            filename = f'{self.name}.json'
        else:
            # Avoid file name being too long. 255 bytes seems common. Leave
            # some headroom for multibytes.
            # https://en.wikipedia.org/wiki/Comparison_of_file_systems#Limits
            max_len = 250 - len(self.name) - len('..json')
            cache_id_str = self._cache_data_as_string(cache_id)
            if len(cache_id_str) > max_len:
                cache_id_str = ''.join((
                    cache_id_str[:int(max_len / 2 - 1)],
                    '…',
                    cache_id_str[-int(max_len / 2 - 1):],
                ))
            if cache_id_str:
                filename = f'{self.name}.{cache_id_str}.json'
            else:
                filename = f'{self.name}.json'
            filename = fs.sanitize_filename(filename)
        return os.path.join(self.cache_directory, filename)

    @cached_property
    def cache_id(self):
        """
        Unique object based on the job's input data

        The return value is turned into a string. Items of non-string iterables
        are passed to :class:`str` and :meth:`~.str.join`\\ ed with ",".

        If this property returns `None`, cache is not read or written.

        The default implementation uses the arguments passed to
        :meth:`initialize`.
        """
        return self._kwargs

    def _cache_data_as_string(self, value):
        if isinstance(value, collections.abc.Mapping):
            return ','.join((f'{k}-{self._cache_data_as_string(v)}' for k, v in value.items()))

        elif isinstance(value, collections.abc.Iterable) and not isinstance(value, str):
            return ','.join((self._cache_data_as_string(v) for v in value))

        elif isinstance(value, (str, os.PathLike)) and os.path.exists(value):
            # Use same cache file for absolute and relative paths
            return str(os.path.realpath(value))

        else:
            return str(value)
