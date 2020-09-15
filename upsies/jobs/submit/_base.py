import abc
import enum

from ... import __project_name__, __version__, errors
from ...utils import cache
from .. import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmissionJobBase(_base.JobBase, abc.ABC):
    name = 'submission'
    label = 'Submission'
    timeout = 180

    @cache.property
    def _http_session(self):
        import aiohttp
        return aiohttp.ClientSession(
            headers={'User-Agent': f'{__project_name__}/{__version__}'},
            raise_for_status=True,
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        )

    async def http_get(self, url, **params):
        """
        Send HTTP GET request

        Use this method for sending requests to the tracker.
        Use :mod:`utils.http` for other domains.

        :param str url: Request URL
        :param params: Arguments for `aiohttp.ClientSession.get`

        :raise RequestError: if the request fails for any reason
        :return: `aiohttp.ClientResponse` object
        """
        import aiohttp
        try:
            return await self._http_session.get(url, **params)
        except aiohttp.ClientResponseError as e:
            raise errors.RequestError(f'{url}: {e.message}')
        except aiohttp.ClientError as e:
            raise errors.RequestError(f'{url}: {e}')

    async def http_post(self, url, **params):
        """
        Send HTTP POST request

        Use this method for sending requests to the tracker.
        Use :mod:`utils.http` for other domains.

        :param str url: Request URL
        :param params: Arguments for `aiohttp.ClientSession.post`

        :raise RequestError: if the request fails for any reason
        :return: `aiohttp.ClientResponse` object
        """
        import aiohttp
        try:
            return await self._http_session.post(url, **params)
        except aiohttp.ClientResponseError as e:
            raise errors.RequestError(f'{url}: {e.message}')
        except aiohttp.ClientError as e:
            raise errors.RequestError(f'{url}: {e}')

    @staticmethod
    def parse_html(string):
        """
        Return `BeautifulSoup` instance

        :param string: HTML document
        """
        from bs4 import BeautifulSoup
        return BeautifulSoup(string, features='html.parser')

    def dump_html(self, filename, html):
        """
        Write `html` to `filename`

        Used for debugging unexpected exceptions.
        """
        with open('login.html', 'w') as f:
            f.write(html)

    def initialize(self, args, config, content_path):
        self._args = args
        self._config = config
        self._content_path = str(content_path)
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

    async def _submit(self):
        _log.debug('%s: Submitting %s', self.trackername, self.content_path)
        try:
            self._call_callbacks(self.signal.logging_in)
            await self.login()
            self._call_callbacks(self.signal.logged_in)
            try:
                self._call_callbacks(self.signal.submitting)
                torrent_page_url = await self.upload()
                self.send(torrent_page_url)
                self._call_callbacks(self.signal.submitted)
            finally:
                self._call_callbacks(self.signal.logging_out)
                await self.logout()
                self._call_callbacks(self.signal.logged_out)
        except errors.RequestError as e:
            self.error(e)
        finally:
            await self._http_session.close()
            assert self._http_session.closed

    class signal(enum.Enum):
        logging_in = 1
        logged_in = 2
        submitting = 3
        submitted = 4
        logging_out = 5
        logged_out = 6

    def on(self, status, callback):
        """
        Run `callback` when status is set to `status`

        :param status: When to call `callback`
        :type status: Any attribute of :attr:`signal`
        :param callable callback: Callable that doesn't take any arguments
        """
        if not isinstance(status, self.signal):
            raise RuntimeError(f'Unknown callback: {status!r}')
        else:
            self._callbacks[status].append(callback)

    def _call_callbacks(self, status):
        for cb in self._callbacks[status]:
            cb()
