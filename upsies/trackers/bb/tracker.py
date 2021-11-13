"""
Concrete :class:`~.base.TrackerBase` subclass for bB
"""

import asyncio
import re
import urllib

from ... import errors
from ...utils import html, http
from ..base import TrackerBase
from .config import BbTrackerConfig
from .jobs import BbTrackerJobs

import logging  # isort:skip
_log = logging.getLogger(__name__)


class BbTracker(TrackerBase):
    name = 'bb'
    label = 'bB'

    TrackerConfig = BbTrackerConfig
    TrackerJobs = BbTrackerJobs

    _url_path = {
        'login': '/login.php',
        'logout': '/logout.php',
        'upload': '/upload.php',
        'torrent': '/torrents.php',
    }

    _max_login_attempts = 30
    _login_retry_delay = 1
    _login_retry_delay_max = 3

    async def login(self):
        if not self.is_logged_in:
            if not self.options.get('username'):
                raise errors.RequestError('Login failed: No username configured')
            elif not self.options.get('password'):
                raise errors.RequestError('Login failed: No password configured')

            login_url = urllib.parse.urljoin(
                self.options['base_url'],
                self._url_path['login'],
            )

            doc = html.parse('')
            while await self._work_around_login_bug(doc):
                _log.debug('%s: Logging in as %r', self.name, self.options['username'])
                response = await http.post(
                    url=login_url,
                    user_agent=True,
                    data={
                        'username': self.options['username'],
                        'password': self.options['password'],
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
            html.dump(doc, 'login.html')
            raise errors.RequestError('Login failed: No error message found. See login.html.')

    async def _work_around_login_bug(self, doc):
        # Login sometimes fails and redirects to main page without logging in
        if not self._get_auth_token(doc):
            if not hasattr(self, '_login_attempts'):
                self._login_attempts = -1
            self._login_attempts += 1

            if self._login_attempts < self._max_login_attempts:
                if self._login_attempts:
                    self._login_retry_delay = min(self._login_retry_delay * 1.2,
                                                  self._login_retry_delay_max)
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
        logout_link_tag = doc.find('a', href=cls._auth_token_regex)
        if logout_link_tag:
            logout_link_href = logout_link_tag['href']
            if logout_link_href:
                match = cls._auth_token_regex.search(logout_link_href)
                if match:
                    return match.group(1)

    def _store_auth_token(self, doc):
        auth_token = self._get_auth_token(doc)
        if not auth_token:
            raise RuntimeError('Failed to find authentication token')
        else:
            self._auth_token = auth_token

    @property
    def is_logged_in(self):
        return bool(getattr(self, '_auth_token', False))

    async def logout(self):
        if self.is_logged_in:
            _log.debug('%s: Logging out', self.name)
            logout_url = urllib.parse.urljoin(
                self.options['base_url'],
                self._url_path['logout'],
            )
            params = {'auth': self._auth_token}
            delattr(self, '_auth_token')
            await http.get(url=logout_url, params=params, user_agent=True)

    async def get_announce_url(self):
        url = urllib.parse.urljoin(
            self.options['base_url'],
            self._url_path['upload'],
        )
        _log.debug('%s: Getting announce URL from %s', self.name, url)
        response = await http.get(url, cache=False, user_agent=True)
        doc = html.parse(response)
        announce_url_tag = doc.find('input', value=re.compile(r'^https?://.*/announce$'))
        if announce_url_tag:
            return announce_url_tag['value']
        else:
            _log.debug('%s: Failed to find announce URL', self.name)

    async def upload(self, tracker_jobs):
        _log.debug('Uploading %r', tracker_jobs.post_data)
        upload_url = urllib.parse.urljoin(self.options['base_url'], self._url_path['upload'])
        response = await http.post(
            url=upload_url,
            cache=False,
            user_agent=True,
            follow_redirects=False,
            files={'file_input': {
                'file': tracker_jobs.torrent_filepath,
                'mimetype': 'application/octet-stream',
            }},
            data=tracker_jobs.post_data,
        )

        # Upload response should redirect to torrent page via "Location" header
        torrent_page_url = urllib.parse.urljoin(
            self.options['base_url'],
            response.headers.get('Location', ''),
        )
        if urllib.parse.urlparse(torrent_page_url).path == self._url_path['torrent']:
            return str(torrent_page_url)
        else:
            _log.debug('Unexpected torrent page URL: %r', torrent_page_url)
            doc = html.parse(response)

            # Try to find error message
            error_tag = doc.find('p', style=re.compile(r'color: red'))
            try:
                error_msg = error_tag.string.strip()
                if error_msg:
                    raise errors.RequestError(f'Upload failed: {error_msg}')
            except AttributeError:
                pass

            # Try to find different type of error message
            # (e.g. "The exact same torrent file already exists on the site!")
            try:
                error_header_tag = doc.find('h2', string=re.compile(r'^\s*Error\s*$'))
                parent_tag = error_header_tag.parent
                error_msg_tag = parent_tag.find('p')
                error_msg = error_msg_tag.string.strip()
                if error_msg:
                    raise errors.RequestError(f'Upload failed: {error_msg}')
            except AttributeError:
                pass

            # Try to find warning (e.g. "Your torrent has been uploaded however,
            # you must re-download the torrent file from <a
            # href="torrents.php?id=123456">here</a>, because of the following
            # warnings: The torrent did not have the correct announce URL."
            try:
                warning_header_tag = doc.find('h1', string=re.compile(r'^\s*Warning\s*$'))
                content_tag = warning_header_tag.parent
                warnings = [
                    warning_tag.get_text().strip()
                    for warning_tag in content_tag.find_all('li')
                ]
                if warnings:
                    for warning in warnings:
                        self.warn(warning)
                    return None
            except AttributeError:
                pass

            # Unable to find error message
            html.dump(response, 'upload.html')
            raise RuntimeError('Failed to find error message. See upload.html.')
