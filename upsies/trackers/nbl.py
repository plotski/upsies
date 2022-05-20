"""
Concrete :class:`~.base.TrackerConfigBase`, :class:`~.base.TrackerJobsBase`
and :class:`~.base.TrackerBase` subclasses for NBL
"""

import base64
import re

from .. import errors
from ..utils import cached_property, configfiles, http
from . import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class NblTrackerConfig(base.TrackerConfigBase):
    defaults = {
        'upload_url': base64.b64decode('aHR0cHM6Ly9uZWJ1bGFuY2UuaW8vdXBsb2FkLnBocA==').decode('ascii'),
        'announce_url': configfiles.config_value(
            value='',
            description=(
                'The complete announce URL with your private passkey.\n'
                'Get it from the website: Shows -> Upload -> Your personal announce URL'
            ),
        ),
        'apikey': configfiles.config_value(
            value='',
            description=(
                'Your personal private API key.\n'
                'Get it from the website: <USERNAME> -> Settings -> API keys'
            ),
        ),
        'source': 'NBL',
        'exclude': [],
    }

    argument_definitions = {
        # Custom arguments, e.g. "upsies submit nbl --foo bar"
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
        return self.make_choice_job(
            name=self.get_job_name('category'),
            label='Category',
            autodetected=str(self.release_name.type),
            options=(
                {'label': 'Season', 'value': '3', 'regex': re.compile(r'^(?i:season)$')},
                {'label': 'Episode', 'value': '1', 'regex': re.compile(r'^(?i:episode)$')},
            ),
        )

    @property
    def post_data(self):
        return {
            'api_key': self.options['apikey'],
            'category': self.get_job_attribute(self.category_job, 'choice'),
            'tvmazeid': self.get_job_output(self.tvmaze_job, slice=0),
            'mediainfo': self.get_job_output(self.mediainfo_job, slice=0),
        }

    @property
    def torrent_filepath(self):
        return self.get_job_output(self.create_torrent_job, slice=0)


class NblTracker(base.TrackerBase):
    name = 'nbl'
    label = 'NBL'

    TrackerConfig = NblTrackerConfig
    TrackerJobs = NblTrackerJobs

    async def login(self):
        pass

    @property
    def is_logged_in(self):
        return True

    async def logout(self):
        pass

    async def get_announce_url(self):
        return self.options['announce_url']

    def get_upload_url(self):
        return self.options['upload_url']

    async def upload(self, tracker_jobs):
        if not self.options['apikey']:
            raise errors.RequestError('No API key configured')

        _log.debug('Uploading to %r', self.get_upload_url())

        # Remove None and empty strings from post_data but keep any int(0)
        # values. Also ensure all keys and values are strings.
        post_data = {
            str(k): str(v)
            for k, v in tracker_jobs.post_data.items()
            if v not in (None, '')
        }
        _log.debug('POST data: %r', post_data)

        files = {
            'file_input': {
                'file': tracker_jobs.torrent_filepath,
                'mimetype': 'application/x-bittorrent',
            },
        }
        _log.debug('Files: %r', files)

        try:
            response = await http.post(
                url=self.get_upload_url(),
                cache=False,
                user_agent=True,
                data=post_data,
                files=files,
            )
        except errors.RequestError as e:
            _log.debug(f'Request failed: {e!r}')
            _log.debug(f'url={e.url!r}')
            _log.debug(f'text={e.text!r}')
            _log.debug(f'headers={e.headers!r}')
            _log.debug(f'status_code={e.status_code!r}')
            # The error message in the HTTP response is JSON. Try to parse that
            # to get the actual error message. If that fails, raise the
            # RequestError as is.
            json = e.json(default=False)
            if not json:
                raise errors.RequestError(f'Upload failed: {e.text}')
        else:
            _log.debug('Upload response: %r', response)
            json = response.json()

        # NOTE: It seems that none of the keys in the returned JSON are
        #       guaranteed to exist.
        _log.debug('Upload JSON response: %r', json)
        _log.debug(json.get('status'))
        if json.get('status') == 'success':
            return tracker_jobs.torrent_filepath
        elif json.get('message'):
            raise errors.RequestError(f'Upload failed: {json["message"]}')
        elif json.get('error'):
            raise errors.RequestError(f'Upload failed: {json["error"]}')
        else:
            raise RuntimeError(f'Unexpected response: {json!r}')
