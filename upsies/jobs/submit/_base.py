import abc
import enum

import bs4

from ... import __project_name__, __version__, errors
from ...utils import LazyModule, cache
from .. import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)

aiohttp = LazyModule(module='aiohttp', namespace=globals())


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

    def initialize(self, *, args, config, content_path):
        self._args = args
        self._config = config
        self._content_path = content_path
        self._callbacks = {
            self.signal.logging_in: [],
            self.signal.logged_in: [],
            self.signal.submitting: [],
            self.signal.submitted: [],
            self.signal.logging_out: [],
            self.signal.logged_out: [],
        }

    def execute(self):
        pass

    @property
    def config(self):
        """Configuration from config file as dictionary"""
        return self._config

    @property
    def args(self):
        """CLI arguments as namespace"""
        return self._args

    @property
    def content_path(self):
        """Path to content file(s)"""
        return self._content_path

    @property
    @abc.abstractmethod
    def trackername(self):
        """Tracker name abbreviation"""
        pass

    @abc.abstractmethod
    async def login(self):
        """Authenticate a user and start a session"""
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
    @abc.abstractmethod
    def jobs(self):
        """
        Sequence of instances of :class:`JobBase`

        The last job must be the instance of this class.
        """
        pass

    async def wait(self):
        # Wait for all subjobs (e.g. torrent creation)
        for job in self.jobs:
            if job is not self:
                await job.wait()

        # Maybe user aborted
        if not self.is_finished:
            await self._submit()
            self.finish()

    @cache.property
    def _http_session(self):
        return aiohttp.ClientSession(
            headers={'User-Agent': f'{__project_name__}/{__version__}'},
            raise_for_status=True,
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        )

    async def _submit(self):
        _log.debug('%s: Submitting %s', self.trackername, self.content_path)
        try:
            async with self._http_session as client:
                self._call_callbacks(self.signal.logging_in)
                await self.login(client)
                self._call_callbacks(self.signal.logged_in)
                try:
                    self._call_callbacks(self.signal.submitting)
                    torrent_page_url = await self.upload(client)
                    self.send(torrent_page_url)
                    self._call_callbacks(self.signal.submitted)
                finally:
                    self._call_callbacks(self.signal.logging_out)
                    await self.logout(client)
                    self._call_callbacks(self.signal.logged_out)
        except errors.RequestError as e:
            self.error(e)

    class signal(enum.Enum):
        logging_in = 1
        logged_in = 2
        submitting = 3
        submitted = 4
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
