import abc
import asyncio
import json
import os

from .. import errors

import logging  # isort:skip
_log = logging.getLogger(__name__)


class JobBase(abc.ABC):
    """Base class for all jobs"""

    @property
    @abc.abstractmethod
    def name(self):
        """Internal name"""
        pass

    @property
    @abc.abstractmethod
    def label(self):
        """User-facing name"""
        pass

    @property
    def homedir(self):
        """Directory where any output or other files should go in"""
        return self._homedir

    def __init__(self, *, homedir, ignore_cache, **kwargs):
        self._homedir = homedir
        self._ignore_cache = ignore_cache
        self._errors = []
        self._output = []
        self._output_callbacks = []
        self._finished_event = asyncio.Event()
        self._kwargs = kwargs
        self.initialize(**kwargs)

    @abc.abstractmethod
    def initialize(self):
        """
        Called after job creation

        This method should do handle arguments and return quickly.
        """
        pass

    @abc.abstractmethod
    def execute(self):
        """Called when this job is supposed to do work"""
        pass

    def start(self):
        """
        Called by the main entry point when this job is executed

        If there is cached output available, load it and mark this job as
        finished. Otherwise, call :meth:`execute`.
        """
        _log.debug('Running %r', self)
        self.read_output_cache()
        if self.output:
            _log.debug('Job was already done previously %r', self)
            self._finished_event.set()
        else:
            _log.debug('Executing %r', self)
            self.execute()

    async def wait(self):
        """
        Wait for this job to finish

        This method must be called. :attr:`is_finished` must be `False` before
        this method returns and `True` afterwards.
        """
        await self._finished_event.wait()

    def finish(self):
        """
        Mark this job as finished

        When this method is called, :meth:`wait` must return and
        :attr:`is_finished` must be `True`.
        """
        if not self.is_finished:
            self._finished_event.set()
            self.write_output_cache()

    @property
    def is_finished(self):
        """Whether this job is done"""
        return self._finished_event.is_set()

    @property
    def output(self):
        """Result of this job as a sequence of strings"""
        return tuple(self._output)

    @property
    def info(self):
        """Additional information that is only displayed but not the job's result"""
        return ''

    @property
    def exit_code(self):
        """`0` if job was successful, `> 0` otherwise"""
        if self.is_finished:
            return 0 if self.output and not self.errors else 1

    @property
    def errors(self):
        """Sequence of reported errors (strings or exceptions)"""
        return tuple(self._errors)

    def error(self, error, if_not_finished=False):
        """
        Append `error` to :attr:`errors`

        :param bool if_not_finished: Ignore this call if :attr:`is_finished` is
            True
        """
        if not self.is_finished:
            self._errors.append(error)
        else:
            if not if_not_finished:
                raise RuntimeError('error() called on finished job')

    def send(self, output, if_not_finished=False):
        """
        Append `output` to :attr:`output`

        :param bool if_not_finished: Ignore this call if :attr:`is_finished` is
            True
        """
        if not self.is_finished:
            self._output.append(str(output))
        else:
            if not if_not_finished:
                raise RuntimeError('send() called on finished job')

    def write_output_cache(self):
        """
        Store :attr:`output` in :attr:`cache_file`

        The base class implementation caches output as JSON. Derivative classes
        may want to use other formats.

        :raise RuntimeError: if :attr:`output` is not JSON-encodable or
            :attr:`cache_file` exists unwritable
        """
        if self.output:
            _log.debug('Writing output cache: %r: %r', self.cache_file, self.output)
            try:
                output_string = json.dumps(self.output)
            except (ValueError, TypeError) as e:
                raise RuntimeError(f'Unable to encode output as JSON: {self.output!r}: {e}')
            else:
                try:
                    with open(self.cache_file, 'w') as f:
                        f.write(output_string)
                        f.write('\n')
                except OSError as e:
                    raise RuntimeError(f'Unable to write cache {self.cache_file}: {e}')

    def read_output_cache(self):
        """
        Set :attr:`output` to data stored in :attr:`cache_file`

        :raise RuntimeError: if content of :attr:`cache_file` is not
            JSON-decodable or :attr:`cache_file` exists unreadable
        """
        if not self._ignore_cache and os.path.exists(self.cache_file):
            _log.debug('Reading output cache: %r', self.cache_file)
            try:
                with open(self.cache_file, 'r') as f:
                    content = f.read()
            except OSError as e:
                raise RuntimeError(f'Unable to read cache {self.cache_file}: {e}')
            else:
                try:
                    self._output = json.loads(content)
                except (ValueError, TypeError) as e:
                    raise RuntimeError(f'Unable to decode JSON: {content!r}: {e}')
            _log.debug('Read cached output: %r', self._output)
        else:
            _log.debug('Not reading output cache: %r', self.cache_file)

    @property
    def cache_directory(self):
        """Path to directory that stores cache files"""
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

    @property
    def cache_file(self):
        """Path of file to store cached :attr:`output` in"""
        kwargs_str = ','.join(f'{k}={v}' for k, v in self._kwargs.items())
        if kwargs_str:
            filename = f'{self.name}:{kwargs_str.replace("/", "_")}.json'
        else:
            filename = f'{self.name}.json'
        _log.debug('Cache file name: %r', filename)
        return os.path.join(self.cache_directory, filename)
