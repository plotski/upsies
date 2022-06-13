"""
Concrete :class:`~.base.TrackerBase` subclass for NBL
"""

from ... import errors
from ...utils import http
from .. import base
from .config import NblTrackerConfig
from .jobs import NblTrackerJobs

import logging  # isort:skip
_log = logging.getLogger(__name__)


class NblTracker(base.TrackerBase):
    name = 'nbl'
    label = 'NBL'

    setup_howto_template = (
        '{howto.introduction}\n'
        '\n'
        '{howto.current_section}. Announce URL\n'
        '\n'
        '   {howto.current_section}.1 On the website, go to Shows -> Upload and copy the ANNOUNCE_URL.\n'
        '   {howto.current_section}.2 $ upsies set trackers.nbl.announce_url ANNOUNCE_URL\n'
        '{howto.bump_section}'
        '\n'
        '{howto.current_section}. API key\n'
        '\n'
        '   {howto.current_section}.1 On the website, go to USERNAME -> Settings and scroll down\n'
        '       to "API keys".\n'
        '   {howto.current_section}.2 Tick the "New Key" and the "Upload" boxes.\n'
        '   {howto.current_section}.3 Click on "Save Profile".\n'
        '   {howto.current_section}.4 Scroll down to "API keys" again and copy the new API_KEY.\n'
        '   {howto.current_section}.5 $ upsies set trackers.nbl.apikey API_KEY\n'
        '{howto.bump_section}'
        '\n'
        '{howto.autoseed}\n'
        '\n'
        '{howto.upload}\n'
    )

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
