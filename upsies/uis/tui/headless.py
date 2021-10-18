"""
Non-interactive job manager

This should be used instead of :class:`~.tui.TUI` when :func:`~.utils.is_tty`
returns `False`.

Headless usage is limited to :attr:`~.jobs.base.JobBase.hidden` jobs.
"""

import sys

from ... import errors, utils

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Headless:
    def __init__(self):
        self._jobs = {}
        self._exception = None

    def add_jobs(self, *jobs):
        """Add :class:`~.jobs.base.JobBase` instances"""
        for job in jobs:
            if job.name in self._jobs:
                raise RuntimeError(f'Job was already added: {job.name}')
            elif not job.hidden:
                raise errors.UiError('Headless mode is not supported for this command.')
            else:
                self._jobs[job.name] = job

                # Terminate application if all jobs finished
                job.signal.register('finished', self._exit_if_all_jobs_finished)

                # Terminate application if any job finished with non-zero exit code
                job.signal.register('finished', self._exit_if_job_failed)

    def run(self, jobs):
        """
        Block while running `jobs`

        :param jobs: Iterable of :class:`~.jobs.base.JobBase` instances

        :raise: Any exception that occured while running jobs

        :return: :attr:`~.JobBase.exit_code` from the first failed job or 0 for
            success
        """
        self.add_jobs(*jobs)

        for job in self._enabled_jobs:
            _log.debug('Starting job: %r', job.name)
            job.start()
        utils.get_aioloop().run_until_complete(self._wait_for_jobs())

        # First non-zero exit_code is the application exit_code
        for job in self._enabled_jobs:
            _log.debug('Checking exit_code of %r: %r', job.name, job.exit_code)
            if job.exit_code != 0:
                for error in job.errors:
                    print(f'{job.name}: {error}', file=sys.stderr)
                return job.exit_code
        return 0

    @property
    def _enabled_jobs(self):
        return tuple(job for job in self._jobs.values() if job.is_enabled)

    def _exit_if_all_jobs_finished(self, *_):
        if all(job.is_finished for job in self._enabled_jobs):
            _log.debug('All jobs finished')
            self._finish_jobs()

    def _exit_if_job_failed(self, job):
        if job.is_finished and job.exit_code != 0:
            _log.debug('Terminating application because of failed job: %r', job.name)
            self._finish_jobs()

    async def _wait_for_jobs(self):
        _log.debug('Terminating all jobs')
        for job in self._enabled_jobs:
            if job.is_started and not job.is_finished:
                _log.debug('Waiting for %r', job.name)
                await job.wait()
                _log.debug('Done waiting for %r', job.name)

    def _finish_jobs(self):
        for job in self._enabled_jobs:
            if not job.is_finished:
                _log.debug('Finishing %s', job.name)
                job.finish()
