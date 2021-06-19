"""
Concrete :class:`~.base.TrackerConfigBase`, :class:`~.base.TrackerJobsBase`
and :class:`~.base.TrackerBase` subclasses for NBL
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
        return jobs.dialog.ChoiceJob(
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
        if not self.is_logged_in:
            if not self.options.get('username'):
                raise errors.RequestError('Login failed: No username configured')
            elif not self.options.get('password'):
                raise errors.RequestError('Login failed: No password configured')

            _log.debug('%s: Logging in as %r', self.name, self.options['username'])
            login_url = urllib.parse.urljoin(
                self.options['base_url'],
                self._url_path['login'],
            )
            response = await http.post(
                url=login_url,
                user_agent=True,
                data={
                    'username': self.options['username'],
                    'password': self.options['password'],
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
            _log.debug('%s: Logged in as %r', self.name, self.options['username'])
            self._logout_url = urllib.parse.urljoin(
                self.options['base_url'],
                logout_url['href'],
            )
            _log.debug('%s: Logout URL: %s', self.name, self._logout_url)

    @property
    def is_logged_in(self):
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
            _log.debug('%s: Announce URL: %s', self.name, announce_url_tag['value'])
            return announce_url_tag['value']

    async def upload(self, tracker_jobs):
        if not self.is_logged_in:
            raise RuntimeError('upload() called before login()')

        metadata = self._get_metadata_from_jobs(tracker_jobs)
        _log.debug('%s: Torrent: %r', self.name, metadata['torrent_filepath'])
        _log.debug('%s: TVmaze ID: %r', self.name, metadata['tvmaze_id'])
        _log.debug('%s: Mediainfo: %r', self.name, metadata['mediainfo'][:100] + '...')
        _log.debug('%s: Category: %r', self.name, metadata['category'])

        post_data = {
            'auth': self._auth_key,
            'title': '',
            'tvmazeid': metadata['tvmaze_id'],
            'media': metadata['mediainfo'],
            'desc': metadata['mediainfo'],
            'mediaclean': f'[mediainfo]{metadata["mediainfo"]}[/mediainfo]',
            'submit': 'true',
            'MAX_FILE_SIZE': '1048576',
            'category': metadata['category'],
            'genre_tags': '',
            'tags': '',
            'image': '',
            'fontfont': '-1',
            'fontsize': '-1',
        }
        if self.options.get('ignore_dupes'):
            post_data['ignoredupes'] = '1'

        upload_url = urllib.parse.urljoin(
            self.options['base_url'],
            self._url_path['upload'],
        )

        response = await http.post(
            url=upload_url,
            user_agent=True,
            allow_redirects=False,
            files={'file_input': {
                'file': metadata['torrent_filepath'],
                'mimetype': 'application/x-bittorrent',
            }},
            data=post_data,
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
            error = doc.find(id='messagebar')
            if error and error.string:
                _log.debug('NBL error: %r', doc)
                if 'torrent contained one or more possible dupes' in error.string:
                    msg = f'{error.string}\nUse --ignore-dupes to enforce the upload.'
                else:
                    msg = error.string
                raise errors.RequestError(f'Upload failed: {msg}')
            else:
                html.dump(str(response), 'upload.html')
                raise RuntimeError('Failed to find error message. See upload.html for more information.')

    def _get_metadata_from_jobs(self, tracker_jobs):

        def translate_category(category):
            if category.lower() == 'episode':
                return '1'
            elif category.lower() == 'season':
                return '3'
            else:
                raise errors.RequestError(f'Unsupported type: {category}')

        return {
            'torrent_filepath': tracker_jobs.create_torrent_job.output[0],
            'tvmaze_id': tracker_jobs.tvmaze_job.output[0],
            'mediainfo': tracker_jobs.mediainfo_job.output[0],
            'category': translate_category(tracker_jobs.category_job.output[0]),
        }
