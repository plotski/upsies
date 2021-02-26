"""
bB API
"""

import asyncio
import base64
import re
import urllib

from .. import errors, jobs
from ..utils import cached_property, html, http
from ..utils.types import ReleaseType
from . import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class BbTrackerConfig(base.TrackerConfigBase):
    defaults = {
        'base_url'   : base64.b64decode('aHR0cHM6Ly9iYWNvbmJpdHMub3Jn').decode('ascii'),
        'username'   : '',
        'password'   : '',
        'exclude'    : [],
        'source'     : 'bB',
        'image_host' : 'imgbox',
    }


class BbTrackerJobs(base.TrackerJobsBase):
    @cached_property
    def jobs_before_upload(self):
        return ()


class BbTracker(base.TrackerBase):
    name = 'bb'
    label = 'bB'

    argument_definitions = {}

    TrackerJobs = BbTrackerJobs
    TrackerConfig = BbTrackerConfig

    _url_path = {
        'login': '/login.php',
        'logout': '/logout.php',
        'upload': '/upload.php',
    }

    _max_login_attempts = 15
    _login_retry_delay = 1

    async def login(self):
        if not self.is_logged_in:
            login_url = urllib.parse.urljoin(
                self.config['base_url'],
                self._url_path['login'],
            )

            doc = html.parse('')
            while await self._work_around_login_bug(doc):
                _log.debug('%s: Logging in as %r', self.name, self.config['username'])
                response = await http.post(
                    url=login_url,
                    user_agent=True,
                    data={
                        'username': self.config['username'],
                        'password': self.config['password'],
                        'login': 'Log In!',
                    },
                )
                doc = html.parse(response)
                self._raise_login_error(doc)

            self._store_auth_token(doc)

    def _raise_login_error(self, doc):
        error_tag = doc.find('font', color='red')
        if error_tag:
            raise errors.RequestError(f'Login failed: {error_tag.string.strip()}')
        elif doc.find('form', id='loginform'):
            raise errors.RequestError('Login failed: No error message found')

    async def _work_around_login_bug(self, doc):
        # Login sometimes fails and redirects to main page without logging in
        if not self._get_auth_token(doc):
            if not hasattr(self, '_login_attempts'):
                self._login_attempts = -1
            self._login_attempts += 1

            if self._login_attempts < self._max_login_attempts:
                if self._login_attempts:
                    self._login_retry_delay = min(self._login_retry_delay * 1.2, 10)
                assert type(self)._login_retry_delay == 1
                if self._login_attempts > 1:
                    _log.debug(f'Encountered login bug; retrying in {round(self._login_retry_delay)}s')
                    await asyncio.sleep(round(self._login_retry_delay))
                return True
            else:
                _log.debug(f'Encountered login bug; giving up after {self._login_attempts} attempts')
                raise errors.RequestError('Login failed: Giving up after encountering '
                                          f'login bug {self._login_attempts} times')
        return False

    _auth_token_regex = re.compile(r'logout\.php\?.*\bauth=([0-9a-fA-F]+)')

    @classmethod
    def _get_auth_token(cls, doc):
        auth_tag = doc.find('a', href=cls._auth_token_regex)
        if auth_tag:
            auth_link = auth_tag['href']
            if auth_link:
                match = cls._auth_token_regex.search(auth_link)
                if match:
                    return match.group(1)

    def _store_auth_token(self, doc):
        auth_token = self._get_auth_token(doc)
        if not auth_token:
            raise RuntimeError('Failed to find authentication token')
        else:
            self._auth_token = auth_token
            _log.debug('%s: Authentication token: %s', self.name, self._auth_token)

    @property
    def is_logged_in(self):
        return bool(getattr(self, '_auth_token', False))

    async def logout(self):
        if self.is_logged_in:
            _log.debug('%s: Logging out', self.name)
            logout_url = urllib.parse.urljoin(
                self.config['base_url'],
                self._url_path['logout'],
            )
            params = {'auth': self._auth_token}
            delattr(self, '_auth_token')
            await http.get(url=logout_url, params=params, user_agent=True)

    async def get_announce_url(self):
        url = urllib.parse.urljoin(
            self.config['base_url'],
            self._url_path['upload'],
        )
        _log.debug('%s: Getting announce URL from %s', self.name, url)
        response = await http.get(url, cache=False, user_agent=True)
        doc = html.parse(response)
        announce_url_tag = doc.find('input', value=re.compile(r'^https?://.*/announce$'))
        if announce_url_tag:
            _log.debug('%s: Announce URL: %s', self.name, announce_url_tag['value'])
            return announce_url_tag['value']

    async def upload(self, metadata):
        _log.debug('%s: Uploading %s', self.name, metadata)
        await asyncio.sleep(2)
        return 'http://bb.local/path/to/uploaded/torrent'
