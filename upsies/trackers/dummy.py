"""
Dummy tracker for testing and debugging
"""

import asyncio
import os

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
            self.scene_check_job,
        )

    @cached_property
    def category_job(self):
        if not self.options['skip_category']:

            def select_release_category(release_name):
                _log.debug('Setting type: %r', release_name.type)
                if release_name.type:
                    self.category_job.focused = release_name.type

            self.release_name_job.signal.register('release_name', select_release_category)

            choices = [(str(t).capitalize(), t) for t in ReleaseType if t]
            return jobs.dialog.ChoiceJob(
                name='category',
                label='Category',
                choices=choices,
                **self.common_job_args,
            )


class DummyTracker(base.TrackerBase):
    name = 'dummy'
    label = 'DuMmY'

    argument_definitions = {
        ('--skip-category', '-C'): {
            'help': 'Do not ask for category',
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
        _log.debug('%s: Logging in with %r', self.name, self.options)
        await asyncio.sleep(self.options['delay'])
        self._is_logged_in = True

    async def logout(self):
        _log.debug('%s: Logging out', self.name)
        await asyncio.sleep(self.options['delay'])
        self._is_logged_in = False

    @property
    def is_logged_in(self):
        return getattr(self, '_is_logged_in', False)

    async def get_announce_url(self):
        _log.debug('%s: Getting announce URL', self.name)
        await asyncio.sleep(self.options['delay'])
        return 'http://localhost:123/f1dd15718/announce'

    async def upload(self, tracker_jobs):
        if tracker_jobs.create_torrent_job.output:
            torrent_file = tracker_jobs.create_torrent_job.output[0]
        else:
            raise errors.RequestError('Torrent file was not created.')
        _log.debug('%s: Uploading %s', self.name, torrent_file)
        await asyncio.sleep(self.options['delay'])
        return f'http://localhost/{os.path.basename(torrent_file)}'
