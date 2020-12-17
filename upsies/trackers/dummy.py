import asyncio
import os

from .. import errors, jobs
from ..utils import ReleaseType, cached_property, release_info
from .base import TrackerBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class DummyTracker(TrackerBase):
    name = 'dummy'
    label = 'DuMmY'

    @cached_property
    def jobs_before_upload(self):
        return (
            self.create_torrent_job,
            self.screenshots_job,
            self.upload_screenshots_job,
            self.mediainfo_job,
            self.imdb_job,
            self.tmdb_job,
            self.release_name_job,
            self.category_job,
        )

    @cached_property
    def category_job(self):
        guess = release_info.ReleaseInfo(self.job_input.content_path).get('type')
        if guess:
            guess = str(guess).capitalize()
        else:
            guess = 'Season'
        return jobs.prompt.ChoiceJob(
            name='category',
            label='Category',
            homedir=self.job_input.homedir,
            ignore_cache=self.job_input.ignore_cache,
            choices=(str(t).capitalize() for t in ReleaseType),
            focused=guess,
        )

    async def login(self):
        _log.debug('Logging in with %r', self.config)
        await asyncio.sleep(1)

    async def logout(self):
        _log.debug('Logging out')
        await asyncio.sleep(1)

    async def upload(self, metadata):
        # Output from torrent job could be empty sequence (error) or None (not
        # finished)
        output = metadata.get('torrent')
        if output:
            torrent_file = output[0]
        else:
            raise errors.RequestError('Something went wrong')
        _log.debug('Uploading %r', torrent_file)
        await asyncio.sleep(1)
        return f'http://localhost/{os.path.basename(torrent_file)}'
