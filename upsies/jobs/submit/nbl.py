import re
import urllib

from ... import errors
from ...tools import mediainfo
from ...utils import cache, fs
from .. import search, torrent
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmissionJob(_base.SubmissionJobBase):
    trackername = 'NBL'

    @cache.property
    def jobs(self):
        return (
            self._torrent_job,
            self._search_job,
            self,
        )

    @cache.property
    def _torrent_job(self):
        return torrent.CreateTorrentJob(
            homedir=fs.projectdir(self.content_path),
            ignore_cache=False,
            content_path=self.content_path,
            exclude_regexs=self.config['exclude'],
            trackername=self.trackername,
            announce_url=self.config['announce'],
            source='NBL',
        )

    @property
    def torrent_filepath(self):
        if self._torrent_job.output:
            return self._torrent_job.output[0]

    @cache.property
    def _search_job(self):
        return search.SearchDbJob(
            homedir=fs.projectdir(self.content_path),
            ignore_cache=False,
            content_path=self.content_path,
            db='tvmaze',
        )

    @property
    def tvmaze_id(self):
        if self._search_job.output:
            return self._search_job.output[0]

    _url_path = {
        'login': '/login.php',
        'upload': '/upload.php',
        'torrent': '/torrents.php',
    }

    async def login(self):
        if not self.logged_in:
            _log.debug('%s: Logging in as %r', self.trackername, self.config['username'])
            login_url = urllib.parse.urljoin(
                self.config['base_url'],
                self._url_path['login'],
            )
            response = await self.http_post(
                url=login_url,
                data={
                    'username': self.config['username'],
                    'password': self.config['password'],
                    'twofa': '',
                    'login': 'Login',
                },
            )
            text = await response.text()
            html = self.parse_html(text)
            self._report_login_error(html)
            self._store_auth_key(html)
            self._store_logout_url(html)

    def _report_login_error(self, html):
        form = html.find(id='loginform')
        if form:
            error = form.find(class_='warning')
            if error:
                msg = error.string.strip()
                if msg:
                    raise errors.RequestError(f'Login failed: {msg}')

    def _store_auth_key(self, html):
        auth_input = html.find('input', {'name': 'auth'})
        if not auth_input:
            self.dump_html('login.html', html.prettify())
            raise RuntimeError('Failed to find input tag named "auth"')
        else:
            self._auth_key = auth_input['value']
            _log.debug('%s: Auth key: %s', self.trackername, self._auth_key)

    def _store_logout_url(self, html):
        logout_url = html.find('a', text=re.compile(r'(?i:Logout)'))
        if not logout_url or not logout_url.get('href'):
            self.dump_html('login.html', html.prettify())
            raise RuntimeError('Failed to find logout URL')
        else:
            _log.debug('%s: Logged in as %r', self.trackername, self.config['username'])
            self._logout_url = urllib.parse.urljoin(
                self.config['base_url'],
                logout_url['href'],
            )
            _log.debug('%s: Logout URL: %s', self.trackername, self._logout_url)

    @property
    def logged_in(self):
        return all(hasattr(self, attr)
                   for attr in ('_logout_url', '_auth_key'))

    async def logout(self):
        if hasattr(self, '_auth_key'):
            delattr(self, '_auth_key')
        if hasattr(self, '_logout_url'):
            logout_url = self._logout_url
            delattr(self, '_logout_url')
            _log.debug('%s: Logging out: %r', self.trackername, logout_url)
            await self.http_get(logout_url)
            _log.debug('%s: Logged out', self.trackername)

    @property
    def mediainfo(self):
        return mediainfo.as_string(self.content_path)

    async def upload(self):
        if not self.torrent_filepath:
            raise RuntimeError('upload() was called before torrent file creation finished')
        _log.debug('%s: Torrent: %r', self.trackername, self.torrent_filepath)

        if not self.tvmaze_id:
            raise RuntimeError('upload() called before TVmaze ID search finished')
        _log.debug('%s: TVmaze ID: %r', self.trackername, self.tvmaze_id)

        import aiohttp
        formdata = aiohttp.FormData()
        formdata.add_field(name='file_input',
                           value=open(self.torrent_filepath, 'rb'),
                           content_type='application/x-bittorrent')
        formdata.add_field('auth', self._auth_key)
        formdata.add_field('title', '')  # Ignored by server
        formdata.add_field('tvmazeid', self.tvmaze_id)
        formdata.add_field('media', self.mediainfo)
        formdata.add_field('desc', self.mediainfo)
        formdata.add_field('mediaclean', f'[mediainfo]{self.mediainfo}[/mediainfo]')
        formdata.add_field('submit', 'true')
        formdata.add_field('MAX_FILE_SIZE', '1048576')
        formdata.add_field('category', '3')
        formdata.add_field('genre_tags', '')
        formdata.add_field('tags', '')
        formdata.add_field('image', '')
        formdata.add_field('fontfont', '-1')
        formdata.add_field('fontsize', '-1')

        upload_url = urllib.parse.urljoin(
            self.config['base_url'],
            self._url_path['upload'],
        )
        response = await self.http_post(upload_url, data=formdata)
        text = await response.text()
        html = self.parse_html(text)

        # The upload form should have redirected use to the torrent page
        if response.url.path.strip('/') == self._url_path['torrent'].strip('/'):
            return response.url
        else:
            _log.debug('Unexpected torrent page URL: %r', response.url)
            # Try to find error message
            error = html.find(id='messagebar')
            if error and error.string:
                raise errors.RequestError(f'Upload failed: {error.string}')
            else:
                self.dump_html('upload.html', html.prettify())
                raise RuntimeError('Failed to find error message')
