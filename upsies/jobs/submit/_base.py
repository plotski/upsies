import abc

from .. import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmissionJobBase(_base.JobBase, abc.ABC):
    name = 'submission'
    label = 'Submission'

    def initialize(self, args, config, content_path):
        self._args = args
        self._config = config
        self._content_path = str(content_path)

    def execute(self):
        pass

    @property
    def config(self):
        """Configuration from config file as dictionary"""
        return self._config

    @property
    def args(self):
        """CLI arguments as namespace"""
        return self._args

    @property
    def content_path(self):
        """Path to content file(s)"""
        return self._content_path

    @property
    @abc.abstractmethod
    def trackername(self):
        """Tracker name abbreviation"""
        pass

    @property
    @abc.abstractmethod
    def jobs(self):
        pass

    @abc.abstractmethod
    async def submit(self):
        pass

    async def wait(self):
        for job in self.jobs:
            if job is not self:
                _log.debug('Waiting for tracker job: %r', job)
                await job.wait()
                _log.debug('Done waiting for tracker job: %r', job)

        # Maybe user aborted
        if not self.is_finished:
            await self.submit()
            self.finish()
