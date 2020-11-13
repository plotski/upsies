import abc
import asyncio
import enum

from ... import __project_name__, __version__, errors
from ...utils import LazyModule, cache
from .. import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)

aiohttp = LazyModule(module='aiohttp', namespace=globals())
bs4 = LazyModule(module='bs4', namespace=globals())


class SubmitJobBase(JobBase, abc.ABC):
    """
    Submit metadata to tracker

    :param tracker_config: Object of any type that can be used for submission
        via the :attr:`tracker_config` attribute

    :param jobs_before_upload: Jobs that must finish before :meth:`upload` can
        be called
    :type jobs_before_upload: iterable of :class:`JobBase` objects
    :param iterable jobs_after_upload: Jobs to call after :meth:`upload`
        finished
    :type jobs_after_upload: iterable of :class:`JobBase` objects
    """

    name = 'submit'
    label = 'Submit'
    timeout = 180

    @staticmethod
    def parse_html(string):
        """
        Return `BeautifulSoup` instance

        :param string: HTML document
        """
        try:
            return bs4.BeautifulSoup(str(string), features='html.parser')
        except Exception as e:
            raise RuntimeError(f'Failed to parse HTML: {e}')

    def dump_html(self, filepath, html):
        """
        Write `html` to `filepath`

        Used for debugging unexpected exceptions.
        """
        with open(filepath, 'w') as f:
            f.write(self.parse_html(str(html)).prettify())

    def initialize(self, *, tracker_config, jobs_before_upload, jobs_after_upload):
        self._tracker_config = tracker_config
        self._jobs_before_upload = tuple(j for j in jobs_before_upload if j)
        self._jobs_after_upload = tuple(j for j in jobs_after_upload if j)
        self._submit_lock = asyncio.Lock()
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
        """Tracker configuration that was passed as keyword argument of same name"""
        return self._tracker_config

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

    @property
    def jobs_before_upload(self):
        """Jobs that must finish before :meth:`upload` can be called"""
        return self._jobs_before_upload

    @property
    def jobs_after_upload(self):
        """Jobs to call after :meth:`upload` finished"""
        return self._jobs_after_upload

    async def wait(self):
        async with self._submit_lock:
            if not self.is_finished:
                _log.debug('Waiting for jobs before submission: %r', self.jobs_before_upload)
                await asyncio.gather(*(job.wait() for job in self.jobs_before_upload))

                names = [job.name for job in self.jobs_before_upload]
                outputs = [job.output for job in self.jobs_before_upload]
                self._metadata.update(zip(names, outputs))
                await self._submit()

                _log.debug('Waiting for jobs after submission: %r', self.jobs_after_upload)
                await asyncio.gather(*(job.wait() for job in self.jobs_after_upload))

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
        _log.debug('%s: Submitting %s', self.tracker_name, self.metadata.get('create-torrent'))
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
