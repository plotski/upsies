import abc
import asyncio
import enum

from ... import __project_name__, __version__, errors
from ...utils import LazyModule, cache
from .. import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)

aiohttp = LazyModule(module='aiohttp', namespace=globals())
bs4 = LazyModule(module='bs4', namespace=globals())


class SubmissionJobBase(_base.JobBase, abc.ABC):
    name = 'submission'
    label = 'Submission'
    timeout = 180

    @staticmethod
    def parse_html(string):
        """
        Return `BeautifulSoup` instance

        :param string: HTML document
        """
        try:
            return bs4.BeautifulSoup(string, features='html.parser')
        except Exception as e:
            raise RuntimeError(f'Failed to parse HTML: {e}')

    @staticmethod
    def dump_html(filepath, html):
        """
        Write `html` to `filepath`

        Used for debugging unexpected exceptions.
        """
        with open(filepath, 'w') as f:
            f.write(html)

    def initialize(self, *, tracker_config, required_jobs):
        self._tracker_config = tracker_config
        self._required_jobs = required_jobs
        self._metadata = {}
        self._callbacks = {
            self.signal.logging_in: [],
            self.signal.logged_in: [],
            self.signal.uploading: [],
            self.signal.uploaded: [],
            self.signal.logging_out: [],
            self.signal.logged_out: [],
        }

    def execute(self):
        pass

    @property
    @abc.abstractmethod
    def tracker_name(self):
        """Tracker name abbreviation"""
        pass

    @property
    def tracker_config(self):
        """Tracker configuration that was passed as a keyword argument"""
        return self._tracker_config

    @property
    def required_jobs(self):
        """
        Sequence of :class:`JobBase` instances that must finish before
        :meth:`upload` is called
        """
        return self._required_jobs

    @abc.abstractmethod
    async def login(self):
        """Start user session"""
        pass

    @abc.abstractmethod
    async def logout(self):
        """End user session"""
        pass

    @abc.abstractmethod
    async def upload(self):
        """Upload torrent and other metadata"""
        pass

    @property
    def metadata(self):
        """
        Dictionary that maps job names to their output

        This dictionary is empty until all required jobs are finished.

        Keys are the jobs' `name` attributes.
        Values are the jobs' `output` attributes.
        """
        return self._metadata

    async def wait(self):
        _log.debug('Waiting for required jobs: %r', self._required_jobs)
        await asyncio.gather(*(job.wait() for job in self._required_jobs))
        names = [job.name for job in self._required_jobs]
        outputs = [job.output for job in self._required_jobs]
        self._metadata.update(zip(names, outputs))
        await self._submit()
        self.finish()
        await super().wait()

    @cache.property
    def _http_session(self):
        return aiohttp.ClientSession(
            headers={'User-Agent': f'{__project_name__}/{__version__}'},
            raise_for_status=True,
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        )

    async def _submit(self):
        _log.debug('%s: Submitting %s', self.tracker_name, self.metadata['create-torrent'])
        try:
            async with self._http_session as client:
                self._call_callbacks(self.signal.logging_in)
                await self.login(client)
                self._call_callbacks(self.signal.logged_in)
                try:
                    self._call_callbacks(self.signal.uploading)
                    torrent_page_url = await self.upload(client)
                    self.send(torrent_page_url)
                    self._call_callbacks(self.signal.uploaded)
                finally:
                    self._call_callbacks(self.signal.logging_out)
                    await self.logout(client)
                    self._call_callbacks(self.signal.logged_out)
        except errors.RequestError as e:
            self.error(e)

    class signal(enum.Enum):
        logging_in = 1
        logged_in = 2
        uploading = 3
        uploaded = 4
        logging_out = 5
        logged_out = 6

    def on(self, signal, callback):
        """
        Run `callback` when `signal` happens

        :param signal: When to call `callback`
        :type signal: Any attribute of :attr:`signal`
        :param callable callback: Callable that doesn't take any arguments
        """
        if not isinstance(signal, self.signal):
            raise RuntimeError(f'Unknown signal: {signal!r}')
        else:
            self._callbacks[signal].append(callback)

    def _call_callbacks(self, signal):
        for cb in self._callbacks[signal]:
            cb()
