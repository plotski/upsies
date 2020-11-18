import asyncio
import os
import random

from .. import errors, jobs
from ..utils import cache, fs
from . import TrackerBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Tracker(TrackerBase):
    name = 'DUMMY'

    @cache.property
    def jobs_before_upload(self):
        return (
            self.create_torrent_job,
            self.screenshots_job,
            self.upload_screenshots_job,
            self.mediainfo_job,
            self.imdb_job,
            self.tmdb_job,
            self.release_name_job,
            self.choice_prompt_job,
        )

    @cache.property
    def choice_prompt_job(self):
        return jobs.prompt.ChoiceJob(
            name='dummy-choice',
            label='Dummy Choice',
            homedir=fs.projectdir(self.info.content_path),
            ignore_cache=self.info.ignore_cache,
            choices=('Foo', 'Bar', 'Baz'),
            focused=random.choice(('Foo', 'Bar', 'Baz')),
        )

    async def login(self):
        _log.debug('Logging in with %r', self.tracker_config)
        await asyncio.sleep(1)

    async def logout(self):
        _log.debug('Logging out')
        await asyncio.sleep(1)

    async def upload(self, metadata):
        # create-torrent output could be empty sequence or None
        output = metadata.get('create-torrent')
        if output:
            torrent_file = output[0]
        else:
            raise errors.RequestError('Something went wrong')
        _log.debug('Uploading %r', torrent_file)
        await asyncio.sleep(1)
        return f'http://localhost/{os.path.basename(torrent_file)}'
