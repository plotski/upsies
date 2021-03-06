"""
:class:`~.base.TrackerJobsBase` subclass for season and episode submissions
"""

from ... import jobs
from ...utils import cached_property
from .base import BbTrackerJobsBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SeriesBbTrackerJobs(BbTrackerJobsBase):
    def handle_imdb_id(self, id):
        _log.debug('Got IMDb ID: %r', id)

    @cached_property
    def jobs_before_upload(self):
        return (
            self.imdb_job,
            self.title_job,
            # self.create_torrent_job,
            # self.screenshots_job,
        )

    @cached_property
    def title_job(self):
        def validator(text):
            text = text.strip()
            if not text:
                raise ValueError(f'Invalid title: {text}')
            self.release_name.title = text

        return jobs.dialog.TextFieldJob(
            name='series-title',
            label='Title',
            validator=validator,
            **self.common_job_args,
        )

    @property
    def torrent_filepath(self):
        return self.create_torrent_job.output[0]

    @property
    def post_data(self):
        return {
            'type': "TV",
            'title': self.title_job.output[0],
        }
