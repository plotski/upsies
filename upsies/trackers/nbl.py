"""
NBL API
"""

import base64
import re
import urllib

from .. import errors, jobs
from ..utils import cached_property, html, http, release
from . import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class NblTrackerConfig(base.TrackerConfigBase):
    defaults = {
        'base_url'   : base64.b64decode('aHR0cHM6Ly9uZWJ1bGFuY2UuaW8=').decode('ascii'),
        'username'   : '',
        'password'   : '',
        'announce'   : '',
        'exclude'    : [],
        'source'     : 'NBL',
        'image_host' : '',
    }


class NblTrackerJobs(base.TrackerJobsBase):
    @cached_property
    def jobs_before_upload(self):
        return (
            self.create_torrent_job,
            self.mediainfo_job,
            self.tvmaze_job,
            self.category_job,
        )

    @cached_property
    def category_job(self):
        # Season or Episode
        release_info = release.ReleaseInfo(self.content_path)
        if release_info['type'] == release.ReleaseType.episode:
            guessed = 'Episode'
        else:
            guessed = 'Season'
        return jobs.prompt.ChoiceJob(
            name='category',
            label='Category',
            choices=('Season', 'Episode'),
            focused=guessed,
            **self.common_job_args,
        )


class NblTracker(base.TrackerBase):
    name = 'nbl'
    label = 'NBL'

    argument_definitions = {
        ('--ignore-dupes', '-D'): {
            'help': 'Force submission even if the tracker reports duplicates',
            'action': 'store_true',
        },
    }

    TrackerConfig = NblTrackerConfig
    TrackerJobs = NblTrackerJobs

    _url_path = {
        'login': '/login.php',
        'upload': '/upload.php',
        'torrent': '/torrents.php',
    }

    async def login(self):
        if not self.logged_in:
            _log.debug('%s: Logging in as %r', self.name, self.config['username'])
            login_url = urllib.parse.urljoin(
                self.config['base_url'],
                self._url_path['login'],
            )
            response = await http.post(
                url=login_url,
                user_agent=True,
                data={
                    'username': self.config['username'],
                    'password': self.config['password'],
                    'twofa': '',
                    'login': 'Login',
                },
            )
            try:
                doc = html.parse(response)
                self._report_login_error(doc)
                self._store_auth_key(doc)
                self._store_logout_url(doc)
            except Exception:
                html.dump(str(response), 'login.html')
                raise

    def _report_login_error(self, doc):
        def error_tag(tag):
            class_ = tag.get('class', ())
            return (
                'warning' in class_
                and 'hidden' not in class_
                and 'noscript' not in (p.name for p in tag.parents)
            )

        error = doc.find(error_tag)
        if error:
            msg = ' '.join(error.stripped_strings).strip()
            if msg:
                raise errors.RequestError(f'Login failed: {msg}')

    def _store_auth_key(self, doc):
        auth_input = doc.find('input', {'name': 'auth'})
        if not auth_input:
            raise RuntimeError('Failed to find input tag named "auth"')
        else:
            self._auth_key = auth_input['value']
            _log.debug('%s: Auth key: %s', self.name, self._auth_key)

    def _store_logout_url(self, doc):
        logout_url = doc.find('a', text=re.compile(r'(?i:Logout)'))
        if not logout_url or not logout_url.get('href'):
            raise RuntimeError('Failed to find logout URL')
        else:
            _log.debug('%s: Logged in as %r', self.name, self.config['username'])
            self._logout_url = urllib.parse.urljoin(
                self.config['base_url'],
                logout_url['href'],
            )
            _log.debug('%s: Logout URL: %s', self.name, self._logout_url)

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
            _log.debug('%s: Logging out: %r', self.name, logout_url)
            await http.get(logout_url, user_agent=True)

    async def upload(self, metadata):
        _log.debug('Uploading: %r', metadata)
        if not self.logged_in:
            raise RuntimeError('upload() called before login()')

        torrent_filepath = metadata['torrent'][0]
        _log.debug('%s: Torrent: %r', self.name, torrent_filepath)
        tvmaze_id = metadata['tvmaze-id'][0]
        _log.debug('%s: TVmaze ID: %r', self.name, tvmaze_id)
        mediainfo = metadata['mediainfo'][0]
        _log.debug('%s: Mediainfo: %r', self.name, mediainfo[:100] + '...')
        category = metadata['category'][0]
        _log.debug('%s: Category: %r', self.name, category)

        upload_url = urllib.parse.urljoin(
            self.config['base_url'],
            self._url_path['upload'],
        )

        post_data = {
            'auth': self._auth_key,
            'title': '',
            'tvmazeid': tvmaze_id,
            'media': mediainfo,
            'desc': mediainfo,
            'mediaclean': f'[mediainfo]{mediainfo}[/mediainfo]',
            'submit': 'true',
            'MAX_FILE_SIZE': '1048576',
            'category': self._translate_category(category),
            'genre_tags': '',
            'tags': '',
            'image': '',
            'fontfont': '-1',
            'fontsize': '-1',
        }
        if getattr(self.cli_args, 'ignore_dupes', None):
            post_data['ignoredupes'] = '1'

        response = await http.post(
            url=upload_url,
            user_agent=True,
            allow_redirects=False,
            files={'file_input': (torrent_filepath, 'application/x-bittorrent')},
            data=post_data,
        )

        # Upload response should redirect to torrent page via "Location" header
        torrent_page_url = urllib.parse.urljoin(
            self.config['base_url'],
            response.headers.get('Location', ''),
        )
        if urllib.parse.urlparse(torrent_page_url).path == self._url_path['torrent']:
            return str(torrent_page_url)
        else:
            _log.debug('Unexpected torrent page URL: %r', torrent_page_url)
            doc = html.parse(response)
            # Try to find error message
            error = doc.find(id='messagebar')
            if error and error.string:
                raise errors.RequestError(f'Upload failed: {error.string}')
            else:
                html.dump(str(response), 'upload.html')
                raise RuntimeError('Failed to find error message. See upload.html for more information.')

    def _translate_category(self, category):
        if category.lower() == 'episode':
            return '1'
        elif category.lower() == 'season':
            return '3'
        else:
            raise errors.RequestError(f'Unsupported type: {category}')
