import abc
import enum

from ... import __project_name__, __version__, errors
from .. import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmissionJobBase(_base.JobBase, abc.ABC):
    name = 'submission'
    label = 'Submission'

    @property
    def _http_session(self):
        session = getattr(self, '_http_session_', None)
        if not session:
            import aiohttp
            self._http_session_ = session = aiohttp.ClientSession(
                headers={'User-Agent': f'{__project_name__}/{__version__}'},
                raise_for_status=True,
                timeout=aiohttp.ClientTimeout(total=60),
            )
        return session

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
        for job in self.jobs:
            if job is not self:
                _log.debug('Waiting for tracker job: %r', job)
                await job.wait()
                _log.debug('Done waiting for tracker job: %r', job)

        # Maybe user aborted
        if not self.is_finished:
            await self.submit()
            self.finish()

    async def submit(self):
        _log.debug('Submitting %s to %s', self.content_path, self.trackername)
        try:
            self._call_callbacks(self.signal.logging_in)
            await self.login()
            self._call_callbacks(self.signal.logged_in)
            try:
                self._call_callbacks(self.signal.submitting)
                torrent_page_url = await self.upload()
                self._call_callbacks(self.signal.submitted)
                self.send(torrent_page_url)
            finally:
                self._call_callbacks(self.signal.logging_out)
                await self.logout()
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
