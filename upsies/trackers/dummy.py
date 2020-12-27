"""
Dummy tracker for testing and debugging
"""

import asyncio
import os
import pprint

from .. import errors, jobs
from ..utils import ReleaseType, cached_property, release_info
from . import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class DummyTrackerConfig(base.TrackerConfigBase):
    defaults = {
        'base_url'   : 'http://localhost',
        'username'   : '',
        'password'   : '',
        'announce'   : 'http://localhost:12345/dummy/announce',
        'exclude'    : [],
        'source'     : 'DMY',
        'image_host' : 'dummy',
    }


class DummyTrackerJobs(base.TrackerJobsBase):
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
        type = release_info.ReleaseInfo(self.content_path)['type']
        category = self.type2category(type)
        return jobs.prompt.ChoiceJob(
            name='category',
            label='Category',
            choices=(str(t).capitalize() for t in ReleaseType),
            focused=category,
            **self.common_job_args,
        )

    @staticmethod
    def type2category(type):
        if type:
            return str(type).capitalize()
        else:
            return str(ReleaseType.unknown).capitalize()


class DummyTracker(base.TrackerBase):
    name = 'dummy'
    label = 'DuMmY'

    TrackerJobs = DummyTrackerJobs
    TrackerConfig = DummyTrackerConfig

    async def login(self):
        _log.debug('%s: Logging in with %r', self.name, self.config)
        await asyncio.sleep(1)

    async def logout(self):
        _log.debug('%s: Logging out', self.name)
        await asyncio.sleep(1)

    async def upload(self, metadata):
        # Output from torrent job could be empty sequence (error) or None (not
        # finished)
        output = metadata.get('torrent')
        if output:
            torrent_file = output[0]
        else:
            raise errors.RequestError('Something went wrong')
        _log.debug('%s: Uploading %s', self.name, pprint.pformat(metadata))
        await asyncio.sleep(1)
        return f'http://localhost/{os.path.basename(torrent_file)}'
