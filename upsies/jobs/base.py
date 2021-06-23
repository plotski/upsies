"""
Abstract base class for jobs
"""

import abc
import asyncio
import collections
import os
import pickle
import re

import unidecode

from .. import constants
from ..utils import cached_property, fs, signal

import logging  # isort:skip
_log = logging.getLogger(__name__)


class JobBase(abc.ABC):
    """
    Base class for all jobs

    :param str home_directory: Directory that is used to store created files
    :param str cache_directory: Directory that is used to cache output
    :param str ignore_cache: Whether cached output and previously created files
        should not be re-used
    :param bool hidden: Whether to hide the job's output in the UI
    :param bool autostart: Whether this job is started automatically
    :param condition: Callable that gets no arguments and returns whether this
        job is enabled or disabled
    :param callbacks: Mapping of :attr:`signal` names to callable or sequence of
        callables to :meth:`~.signal.Signal.register` for that signal

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
    def home_directory(self):
        """
        Directory that is used to store files (e.g. generated images) or empty
        string

        This directory is guaranteed to exist.
        """
        if self._home_directory and not os.path.exists(self._home_directory):
            fs.mkdir(self._home_directory)
        return self._home_directory

    @cached_property
    def cache_directory(self):
        """
        Path to existing directory that stores :attr:`cache_file`

        This directory is guaranteed to exist.
        """
        if not os.path.exists(self._cache_directory):
            fs.mkdir(self._cache_directory)
        return self._cache_directory

    @property
    def ignore_cache(self):
        """Whether cached output and previously created files should not be re-used"""
        return self._ignore_cache

    @property
    def hidden(self):
        """Whether to hide this job's output in the UI"""
        return self._hidden

    @property
    def autostart(self):
        """
        Whether this job is started automatically

        This property is not used by this class itself. It is only a flag that
        is supposed to be evaluated by any job starting facilities.

        If this value is falsy, :meth:`start` must be called manually.
        """
        return self._autostart

    @property
    def condition(self):
        """Callable that gets no arguments and is called by :attr:`is_enabled`"""
        return self._condition

    @condition.setter
    def condition(self, function):
        if not callable(function):
            raise TypeError(f'Not callable: {function!r}')
        self._condition = function

    @property
    def is_enabled(self):
        """
        Return value of :attr:`condition` as :class:`bool`

        If this value is `False`, this job must not be started nor included in
        the UI.

        This property must be checked by the UI every time any job finishes.
        This job must be started and added to the UI if it changes from `False`
        to `True`.
        """
        return bool(self._condition())

    @property
    def kwargs(self):
        """Keyword arguments from instantiation as :class:`dict`"""
        return self._kwargs

    @property
    def signal(self):
        """
        :class:`~.signal.Signal` instance

        The following signals are added by the base class. Subclasses can add
        their own signals.

        ``finished``
            is emitted when :meth:`finish` is called or when output is read from
            cache. Registered callbacks get the job instance as a positional
            argument.

        ``output``
            is emitted when :meth:`send` is called or when output is read from
            cache. Registered callbacks get the value passed to :meth:`send` as
            a positional argument.

        ``info``
            is emitted when :attr:`info` is set. Registered callbacks get the
            new :attr:`info` as a positional argument.

        ``warning``
            is emitted when :meth:`warn` is called. Registered callbacks get the
            value passed to :meth:`warn` as a positional argument.

        ``error``
            is emitted when :meth:`error` is called. Registered callbacks get
            the value passed to :meth:`error` as a positional argument.
        """
        return self._signal

    def __init__(self, *, home_directory=None, cache_directory=None,
                 ignore_cache=False, hidden=False, autostart=True,
                 condition=None, callbacks={}, **kwargs):
        self._home_directory = home_directory if home_directory else ''
        self._cache_directory = cache_directory if cache_directory else constants.CACHE_DIRPATH
        self._ignore_cache = bool(ignore_cache)
        self._hidden = bool(hidden)
        self._autostart = bool(autostart)
        self.condition = condition or (lambda: True)
        self._is_started = False
        self._is_executed = False
        self._exception = None
        self._output = []
        self._warnings = []
        self._errors = []
        self._info = ''
        self._tasks = []
        self._finished_event = asyncio.Event()

        self._signal = signal.Signal('output', 'info', 'warning', 'error', 'finished')
        self._signal.register('output', lambda output: self._output.append(str(output)))
        self._signal.register('warning', lambda warning: self._warnings.append(warning))
        self._signal.register('error', lambda error: self._errors.append(error))
        self._signal.record('output')

        self._kwargs = kwargs
        self.initialize(**kwargs)

        # Add signal callbacks after `initialize` had the chance to add custom
        # signals.
        for signal_name, callback in callbacks.items():
            if callable(callback):
                self._signal.register(signal_name, callback)
            else:
                for cb in callback:
                    self._signal.register(signal_name, cb)

    def initialize(self):
        """
        Called by :meth:`__init__` with additional keyword arguments

        This method should handle its arguments and return quickly.
        """

    def execute(self):
        """
        Do the job, e.g. ask for user input or start a task or subprocess

        This method must not block.
        """

    def start(self):
        """
        Called by the main entry point when this job is executed

        If there is cached output available, load it and call :meth:`finish`.
        Otherwise, call :meth:`execute`.

        :raise RuntimeError: if this method is called multiple times or if
            reading from cache file fails unexpectedly
        """
        if self.is_enabled:
            if self._is_started:
                raise RuntimeError('start() was already called')
            else:
                self._is_started = True

            try:
                cache_was_read = self._read_cache()
            except BaseException:
                self.finish()
                raise

            if cache_was_read:
                self.finish()
            else:
                _log.debug('Executing job: %s', self.name)
                self._is_executed = True
                self.execute()

    @property
    def is_started(self):
        """Whether :meth:`start` was called"""
        return self._is_started

    async def wait(self):
        """
        Wait for this job to finish

        Subclasses that need to wait for I/O should do so by overriding this
        method.

        Subclasses must call the parent's method (``super().wait()``).

        This method returns when :meth:`finish` is called.

        :attr:`is_finished` is `False` before this method returns and `True`
        afterwards.

        Calling this method multiple times simultaneously is safe.

        :raise: The first exception given to :meth:`exception`
        """
        await self._finished_event.wait()
        if self.raised:
            raise self.raised

    def finish(self):
        """
        Cancel this job if it is not finished yet and emit ``finished`` signal

        Calling this method unblocks any calls to :meth:`wait`.

        :attr:`is_finished` is `True` after this method was called.

        Calling this method from multiple coroutines simultaneously is safe.

        Subclasses must call the parent's method (``super().finish()``).

        This method does not block.
        """
        if not self.is_finished:
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            self._finished_event.set()
            self.signal.emit('finished', self)
            self._write_cache()

    @property
    def is_finished(self):
        """Whether :meth:`finish` was called"""
        return self._finished_event.is_set()

    @property
    def exit_code(self):
        """`0` if job was successful, `> 0` otherwise, None while job is not finished"""
        if self.is_finished:
            if not self.output or self.errors or self.raised:
                return 1
            else:
                return 0

    def send(self, output):
        """Append `output` to :attr:`output` and emit ``output`` signal"""
        if not self.is_finished:
            self.signal.emit('output', str(output))

    @property
    def output(self):
        """Result of this job as an immutable sequence of strings"""
        return tuple(self._output)

    @property
    def info(self):
        """
        String that is only displayed while the job is running and not part of the
        job's output

        Setting this property emits the ``info`` signal.
        """
        return self._info

    @info.setter
    def info(self, info):
        self._info = str(info)
        self.signal.emit('info', info)

    def warn(self, warning):
        """Append `warning` to :attr:`warnings` and emit ``warning`` signal"""
        if not self.is_finished:
            self.signal.emit('warning', str(warning))

    @property
    def warnings(self):
        """
        Sequence of non-critical error messages the user can override or resolve

        Unlike :attr:`errors`, warnings do not imply failure by default.
        """
        return tuple(self._warnings)

    def clear_warnings(self):
        """Empty :attr:`warnings`"""
        if not self.is_finished:
            self._warnings.clear()

    def error(self, error):
        """
        Append `error` to :attr:`errors`, emit ``error`` signal and :meth:`finish`
        this job

        Do nothing if this job is already finished.
        """
        if not self.is_finished:
            self.signal.emit('error', error)
            self.finish()

    @property
    def errors(self):
        """
        Sequence of critical errors (strings or exceptions)

        By default, :attr:`exit_code` is non-zero if any errors were reported.
        """
        return tuple(self._errors)

    def exception(self, exception):
        """
        Make `exception` available as :attr:`raised` and call :meth:`finish`

        .. warning:: Setting an exception means you want to throw a traceback in
                     the user's face.

        :param Exception exception: Exception instance
        """
        if not self.is_finished:
            import traceback
            tb = ''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__))
            _log.debug('Exception in %s: %s', self.name, tb)
            self._exception = exception
            self.finish()

    @property
    def raised(self):
        """Exception passed to :meth:`exception`"""
        return self._exception

    def add_task(self, coro, callback=None, finish_when_done=False):
        """
        Run asynchronous coroutine in a background task and return immediately

        This method should be used to call coroutine functions and other
        awaitables in a synchronous context.

        Any exceptions from `coro` are passed to :meth:`exception`.
        :class:`asyncio.CancelledError` is ignored.

        :param coro: Any awaitable object
        :param callback: Callable that is called with the return value of `coro`
        :param bool finish_when_done: Whether to call :meth:`finish` when `coro`
            is done

        :return: :class:`asyncio.Task` instance
        """

        async def wrapper(coro, callback, finish_when_done):
            try:
                result = await asyncio.ensure_future(coro)
            except asyncio.CancelledError:
                pass
            except BaseException as e:
                _log.debug('%s: Caught %r from %r', self.name, e, coro)
                self.exception(e)
            else:
                if callback:
                    try:
                        callback(result)
                    except BaseException as e:
                        self.exception(e)
                return result
            finally:
                if finish_when_done:
                    _log.debug('Finishing %r because of finished coro: %r', self.name, coro)
                    self.finish()

        async def catch_cancelled_error(coro):
            try:
                return await asyncio.ensure_future(coro)
            except asyncio.CancelledError:
                _log.debug('%s: Cancelled: %r', self.name, coro)

        wrapped = asyncio.ensure_future(
            catch_cancelled_error(
                wrapper(coro, callback, finish_when_done),
            ),
        )
        self._tasks.append(wrapped)
        return wrapped

    async def await_tasks(self):
        """Block until all coroutines passed to :meth:`add_task` are done"""
        for task in self._tasks:
            await task

    def _write_cache(self):
        """
        Store recorded signals in :attr:`cache_file`

        Emitted signals are serialized with :meth:`_serialize_for_cache`.

        :raise RuntimeError: if writing :attr:`cache_file` fails
        """
        if self.signal.emissions and self.exit_code == 0 and self.cache_file and self._is_executed:
            emissions_serialized = self._serialize_for_cache(self.signal.emissions)
            _log.debug('%s: Caching emitted signals: %r', self.name, self.signal.emissions)
            try:
                with open(self.cache_file, 'wb') as f:
                    f.write(emissions_serialized)
                    f.write(b'\n')
            except OSError as e:
                if e.strerror:
                    raise RuntimeError(f'Unable to write cache {self.cache_file}: {e.strerror}')
                else:
                    raise RuntimeError(f'Unable to write cache {self.cache_file}: {e}')

    def _read_cache(self):
        """
        Read cached :attr:`~.signal.Signal.emissions` from :attr:`cache_file`

        Emitted signals are deserialized with :meth:`_deserialize_from_cache`.

        :raise RuntimeError: if :attr:`cache_file` exists and is unreadable

        :return: `True` if cache file was read, `False` otherwise
        """
        if not self._ignore_cache and self.cache_file and os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    emissions_serialized = f.read()
            except OSError as e:
                if e.strerror:
                    raise RuntimeError(f'Unable to read cache {self.cache_file}: {e.strerror}')
                else:
                    raise RuntimeError(f'Unable to read cache {self.cache_file}: {e}')
            else:
                emissions_deserialized = self._deserialize_from_cache(emissions_serialized)
                _log.debug('%s: Replaying cached signals: %r', self.name, emissions_deserialized)
                if emissions_deserialized:
                    self.signal.replay(emissions_deserialized)
                    return True
        return False

    def _serialize_for_cache(self, emissions):
        """
        Convert emitted signals to cache format

        :param emissions: See :attr:`Signal.emissions`

        :return: :class:`bytes`
        """
        return pickle.dumps(emissions, protocol=0, fix_imports=False)

    def _deserialize_from_cache(self, emissions_serialized):
        """
        Convert return value of :meth:`_serialize_for_cache` back to emitted signals

        :param emissions_serialized: :class:`bytes` object

        :return: See :attr:`Signal.emissions`
        """
        return pickle.loads(emissions_serialized)

    _max_filename_len = 255

    @cached_property
    def cache_file(self):
        """
        File path in :attr:`cache_directory` to store cached :attr:`output` in

        If this property returns `None`, cache is not read or written.
        """
        cache_id = self.cache_id
        if cache_id is None:
            return None
        elif not cache_id:
            filename = f'{self.name}.json'
        else:
            # Avoid file name being too long. 255 bytes seems common.
            # https://en.wikipedia.org/wiki/Comparison_of_file_systems#Limits
            max_len = self._max_filename_len - len(self.name) - len('..json')
            cache_id_str = self._cache_id_as_string(cache_id)
            if len(cache_id_str) > max_len:
                cache_id_str = ''.join((
                    cache_id_str[:int(max_len / 2 - 1)],
                    '…',
                    cache_id_str[-int(max_len / 2 - 1):],
                ))
            filename = f'{self.name}.{cache_id_str}.json'
            filename = fs.sanitize_filename(filename)
        return os.path.join(self.cache_directory, filename)

    @cached_property
    def cache_id(self):
        """
        Unique object based on the job's input data

        The return value is turned into a string. If it is a non-string sequence
        or a mapping, items are converted to strings and joined with ",".
        Multibyte characters and directory delimiters are replaced.

        If this property returns `None`, :attr:`cache_file` is not read or
        written.

        If this property returns any other falsy value, :attr:`name` is used.
        """
        return ''

    def _cache_id_as_string(self, value):
        if isinstance(value, collections.abc.Mapping):
            return ','.join((f'{self._cache_id_value_as_string(k)}={self._cache_id_as_string(v)}'
                             for k, v in value.items()))
        elif isinstance(value, collections.abc.Iterable) and not isinstance(value, str):
            return ','.join((self._cache_id_as_string(v) for v in value))
        elif isinstance(value, (str, os.PathLike)) and os.path.exists(value):
            # Use same cache file for absolute and relative paths
            return str(os.path.realpath(value))
        else:
            return self._cache_id_value_as_string(value)

    _object_without_str_regex = re.compile(r'^<.*>$')

    def _cache_id_value_as_string(self, value):
        # Avoid multibyte characters stay below maximum file length
        value_string = unidecode.unidecode(str(value))
        # Check if `value` has a proper string representation to prevent random
        # cache IDs. We don't want "<foo.bar object at 0x...>" in our cache ID.
        if self._object_without_str_regex.search(value_string):
            raise RuntimeError(f'{type(value)!r} has no string representation')
        return value_string


class QueueJobBase(JobBase):
    """
    Subclass of :class:`JobBase` with an :class:`asyncio.Queue`

    This job is used to process input asynchronously, e.g. from another job. For
    example, :meth:`enqueue` from :class:`~.jobs.imghost.ImageHostJob` can be
    connected to the ``output`` :class:`~.utils.signal.Signal` of
    :class:`~.jobs.screenshots.ScreenshotsJob`.

    It's also possible to use this job conventionally by passing a sequence of
    values as the `enqueue` argument. This processes all values and finishes the
    job without waiting for more.

    The :meth:`initialize` method of subclasses must accept `enqueue` as a
    keyword argument.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._queue = asyncio.Queue()
        self._read_queue_task = None
        self._enqueue_args = kwargs.get('enqueue', ())

    def execute(self):
        self._read_queue_task = asyncio.ensure_future(self._read_queue())
        if self._enqueue_args:
            for value in self._enqueue_args:
                self.enqueue(value)
            self.finalize()

    async def _read_queue(self):
        while True:
            value = await self._queue.get()
            if value is None or self.is_finished:
                break
            else:
                try:
                    await self.handle_input(value)
                except BaseException as e:
                    self.exception(e)
                    break
        self.finish()

    @abc.abstractmethod
    async def handle_input(self, value):
        """Handle `value` from queue"""

    def enqueue(self, value):
        """Put `value` in queue"""
        self._queue.put_nowait(value)

    def finalize(self):
        """Finish after all currently queued values are handled"""
        self._queue.put_nowait(None)

    def finish(self):
        """
        Stop reading from queue

        Unlike :meth:`JobBase.finish`, this does not finish the job. The job is
        not finished until :meth:`wait` returns.
        """
        if self._read_queue_task:
            self._read_queue_task.cancel()
        super().finish()

    async def wait(self):
        """Wait for internal queue reading task and finish job"""
        if self._read_queue_task:
            try:
                await self._read_queue_task
            except asyncio.CancelledError:
                pass
        await super().wait()
