"""
Concrete :class:`~.base.TrackerBase` subclass for BHD
"""

import re

from ... import errors, utils
from ..base import TrackerBase
from .config import BhdTrackerConfig
from .jobs import BhdTrackerJobs

import logging  # isort:skip
_log = logging.getLogger(__name__)


class BhdTracker(TrackerBase):
    name = 'bhd'
    label = 'BHD'

    TrackerConfig = BhdTrackerConfig
    TrackerJobs = BhdTrackerJobs

    async def login(self):
        pass

    @property
    def is_logged_in(self):
        return True

    async def logout(self):
        pass

    async def get_announce_url(self):
        return '/'.join((
            self.options['announce_url'].rstrip('/'),
            self.options['announce_passkey'],
        ))

    def get_upload_url(self):
        return '/'.join((
            self.options['upload_url'].rstrip('/'),
            self.options['apikey'],
        ))

    DRAFT_UPLOADED_MESSAGE = 'Draft uploaded'

    async def upload(self, tracker_jobs):
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
            'file': {
                'file': tracker_jobs.torrent_filepath,
                'mimetype': 'application/octet-stream',
            },
            'mediainfo': {
                'file': tracker_jobs.mediainfo_filehandle,
                'filename': 'mediainfo',
                'mimetype': 'application/octet-stream',
            },
        }
        _log.debug('Files: %r', files)

        response = await utils.http.post(
            url=self.get_upload_url(),
            cache=False,
            user_agent=True,
            files=files,
            data=post_data,
        )
        _log.debug('Upload response: %r', response)
        json = response.json()
        _log.debug('Upload response: %r', json)
        try:
            if json['status_code'] == 0:
                # Upload response: {
                #     'status_code': 0,
                #     'status_message': "<error message>",
                #     'success': False,
                # }
                raise errors.RequestError(f'Upload failed: {json["status_message"]}')

            elif json['status_code'] == 1:
                # Upload response: {
                #     'status_code': 1,
                #     'status_message': 'Draft has been successfully saved.',
                #     'success': True,
                # }
                self.warn(json['status_message'])
                self.warn('You have to activate your upload manually '
                          'on the website when you are ready to seed.')
                return tracker_jobs.torrent_filepath

            elif json['status_code'] == 2:
                # Upload response: {
                #     'status_code': 2,
                #     'status_message': '<torrent file URL>',
                #     'success': True,
                # }
                torrent_url = json['status_message']
                return self._torrent_page_url_from_download_url(torrent_url)
            else:
                raise RuntimeError(f'Unexpected response: {str(response)!r}')
        except KeyError:
            raise RuntimeError(f'Unexpected response: {str(response)!r}')

    def _torrent_page_url_from_download_url(self, torrent_download_url):
        # Download URL: .../torrent/download/<torrent name>.123456.d34db33f
        # Website URL: .../torrents/<torrent name>.123456
        torrent_page_url = torrent_download_url.replace('/torrent/download/', '/torrents/')
        torrent_page_url = re.sub(r'\.[a-zA-Z0-9]+$', '', torrent_page_url)
        return torrent_page_url
