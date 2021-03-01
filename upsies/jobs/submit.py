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

    @property
    def cache_id(self):
        """:attr:`.TrackerBase.name`"""
        return self.kwargs['tracker'].name

    def initialize(self, *, tracker, tracker_jobs):
        """
        Set internal state

        :param TrackerBase tracker: Return value of :func:`~.trackers.tracker`
        :param TrackerJobsBase tracker_jobs: Instance of
            :attr:`~.base.TrackerBase.TrackerJobs`
        """
        assert isinstance(tracker, TrackerBase), f'Not a TrackerBase: {tracker!r}'
        assert isinstance(tracker_jobs, TrackerJobsBase), f'Not a TrackerJobsBase: {tracker_jobs!r}'
        self._tracker = tracker
        self._tracker_jobs = tracker_jobs
        self._submit_lock = asyncio.Lock()
        self._run_jobs_task = None
        self._info = ''
        for signal, message in (('logging_in', 'Logging in'),
                                ('logged_in', 'Logged in'),
                                ('uploading', 'Uploading'),
                                ('uploaded', 'Uploaded'),
                                ('logging_out', 'Logging out'),
                                ('logged_out', '')):
            self.signal.add(signal)
            self.signal.register(signal, lambda msg=message: setattr(self, '_info', msg))
        self.signal.register('finished', lambda: setattr(self, '_info', ''))
        self.signal.register('error', lambda _: setattr(self, '_info', ''))

        # Create jobs_after_upload now so they can connect to other jobs,
        # e.g. add_torrent_job needs to register for create_torrent_job's output
        # before create_torrent_job finishes.
        self.jobs_after_upload

        # Start jobs_after_upload only if the upload succeeds. This also works
        # nicely when this job is getting it's output from cache (execute() is
        # not called).
        self.signal.register('output', self._start_jobs_after_upload)

    def _start_jobs_after_upload(self, _):
        for job in self.jobs_after_upload:
            job.start()

    def finish(self):
        """Cancel the asynchronous background task that waits for jobs and finish"""
        # Do not finish any other jobs here. This job might finish immediately
        # with cached output while other jobs are still running. For example,
        # after running "upsies submit ..." the user should be able to run the
        # same command again with "--add-to ..." appended and it shouldn't
        # submit the torrent again and it should wait for the "--add-to ..."
        # job.
        if self._run_jobs_task:
            self._run_jobs_task.cancel()
        super().finish()

    async def wait(self):
        """
        Start the asynchronous background task that waits for jobs and wait for it
        to finish
        """
        async with self._submit_lock:
            if not self.is_finished:
                self._run_jobs_task = asyncio.ensure_future(self._run_jobs())
                try:
                    await self._run_jobs_task
                except asyncio.CancelledError:
                    _log.debug('Submission was cancelled')
                    pass
                finally:
                    self.finish()
        await super().wait()

    async def _run_jobs(self):
        _log.debug('Waiting for jobs before upload: %r', self.jobs_before_upload)
        await asyncio.gather(*(job.wait() for job in self.jobs_before_upload))

        # Ensure all jobs were successful
        if all(job.exit_code == 0 for job in self.jobs_before_upload):
            _log.debug('All jobs_before_upload were successul')
            await self._submit()

    async def _submit(self):
        _log.debug('%s: Submitting', self._tracker.name)
        try:
            self.signal.emit('logging_in')
            await self._tracker.login()
            self.signal.emit('logged_in')
            try:
                self.signal.emit('uploading')
                torrent_page_url = await self._tracker.upload(self._tracker_jobs)
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
        """
        Sequence of jobs to do before submission

        This is the same as :attr:`~TrackerJobsBase.jobs_before_upload` but with
        all `None` values removed.
        """
        return tuple(job for job in self._tracker_jobs.jobs_before_upload if job)

    @utils.cached_property
    def jobs_after_upload(self):
        """
        Sequence of jobs to do after successful submission

        This is the same as :attr:`~TrackerJobsBase.jobs_before_upload` but with
        all `None` values removed.
        """
        return tuple(job for job in self._tracker_jobs.jobs_after_upload if job)

    @property
    def info(self):
        """Current submission status as user-readable string"""
        return self._info
