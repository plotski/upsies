"""
Share generated metadata
"""

import asyncio

from .. import errors, utils
from ..trackers.base import TrackerBase, TrackerJobsBase
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmitJob(JobBase):
    """
    Submit torrent file and other metadata to tracker

    :param TrackerBase tracker: Return value of :func:`~.trackers.tracker`

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``logging_in``
            Emitted when attempting to start a user session. Registered
            callbacks get no arguments.

        ``logged_in``
            Emitted when login attempt ended. Registered callbacks get no
            arguments.

        ``uploading``
            Emitted when attempting to upload metadata. Registered callbacks get
            no arguments.

        ``uploaded``
            Emitted when upload attempt ended. Registered callbacks get no
            arguments.

        ``logging_out``
            Emitted when attempting to end a user session. Registered callbacks
            get no arguments.

        ``logged_out``
            Emitted when logout attempt ended. Registered callbacks get no
            arguments.
    """

    name = 'submit'
    label = 'Submit'
    cache_file = None

    def initialize(self, tracker, tracker_jobs):
        assert isinstance(tracker, TrackerBase), f'Not a TrackerBase: {tracker!r}'
        assert isinstance(tracker_jobs, TrackerJobsBase), f'Not a TrackerJobsBase: {tracker_jobs!r}'
        self._tracker = tracker
        self._tracker_jobs = tracker_jobs
        self._submit_lock = asyncio.Lock()
        self.signal.add('logging_in')
        self.signal.add('logged_in')
        self.signal.add('uploading')
        self.signal.add('uploaded')
        self.signal.add('logging_out')
        self.signal.add('logged_out')

    async def wait(self):
        async with self._submit_lock:
            if not self.is_finished:
                # Create post-upload jobs so they can register signals to
                # connect to pre-upload jobs.
                self.jobs_after_upload

                _log.debug('Waiting for jobs before upload: %r', self.jobs_before_upload)
                await asyncio.gather(*(job.wait() for job in self.jobs_before_upload))
                names = [job.name for job in self.jobs_before_upload]
                outputs = [job.output for job in self.jobs_before_upload]
                metadata = dict(zip(names, outputs))
                await self._submit(metadata)

                for job in self.jobs_after_upload:
                    job.start()
                _log.debug('Waiting for jobs after upload: %r', self.jobs_after_upload)
                await asyncio.gather(*(job.wait() for job in self.jobs_after_upload))

                self.finish()

    async def _submit(self, metadata):
        _log.debug('%s: Submitting %s', self._tracker.name, metadata.get('torrent'))
        try:
            self.signal.emit('logging_in')
            await self._tracker.login()
            self.signal.emit('logged_in')
            try:
                self.signal.emit('uploading')
                torrent_page_url = await self._tracker.upload(metadata)
                self.send(torrent_page_url)
                self.signal.emit('uploaded')
            finally:
                self.signal.emit('logging_out')
                await self._tracker.logout()
                self.signal.emit('logged_out')
        except errors.RequestError as e:
            self.error(e)

    @utils.cached_property
    def jobs_before_upload(self):
        return tuple(job for job in self._tracker_jobs.jobs_before_upload if job)

    @utils.cached_property
    def jobs_after_upload(self):
        return tuple(job for job in self._tracker_jobs.jobs_after_upload if job)
