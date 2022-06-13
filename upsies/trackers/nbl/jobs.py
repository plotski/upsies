"""
Concrete :class:`~.base.TrackerJobsBase` subclass for NBL
"""

import re

from ...utils import cached_property
from .. import base

import logging  # isort:skip
_log = logging.getLogger(__name__)



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
