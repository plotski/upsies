"""
Dummy tracker for testing and debugging
"""

import asyncio
import os
import pprint

from .. import errors, jobs
from ..utils import cached_property
from ..utils.types import ReleaseType
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
        if not self.cli_args.skip_category:
            self.release_name_job.signal.register('release_name', self._handle_release_name)
            return jobs.prompt.ChoiceJob(
                name='category',
                label='Category',
                choices=(str(t).capitalize() for t in ReleaseType if t),
                **self.common_job_args,
            )

    def _handle_release_name(self, release_name):
        _log.debug('Setting type: %r', release_name.type)
        if release_name.type:
            self.category_job.focused = str(release_name.type).capitalize()


class DummyTracker(base.TrackerBase):
    name = 'dummy'
    label = 'DuMmY'

    argument_definitions = {
        ('--skip-category', '-C'): {
            'help': 'Do not prompt for category',
            'action': 'store_true',
        },
        ('--screenshots', '-s'): {
            'help': 'How many screenshots to make',
            'type': int,
            'default': 3,
        },
        ('--delay', '-d'): {
            'help': 'Number of seconds login, upload and logout take each',
            'type': float,
            'default': 1.0,
        },
    }

    TrackerJobs = DummyTrackerJobs
    TrackerConfig = DummyTrackerConfig

    async def login(self):
        _log.debug('%s: Logging in with %r', self.name, self.config)
        await asyncio.sleep(self.cli_args.delay)

    async def logout(self):
        _log.debug('%s: Logging out', self.name)
        await asyncio.sleep(self.cli_args.delay)

    async def upload(self, metadata):
        # Output from torrent job could be empty sequence (error) or None (not
        # finished)
        output = metadata.get('torrent')
        if output:
            torrent_file = output[0]
        else:
            raise errors.RequestError('Torrent file was not created.')
        _log.debug('%s: Uploading %s', self.name, pprint.pformat(metadata))
        await asyncio.sleep(self.cli_args.delay)
        return f'http://localhost/{os.path.basename(torrent_file)}'
