import abc

from .. import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmissionJobBase(_base.JobBase, abc.ABC):
    name = 'submission'
    label = 'Submission'

    @property
    def trackername(self):
        cls = type(self)
        if cls.__module__:
            return cls.__module__.split('.')[-1]

    def initialize(self, args, config, content_path):
        self._args = args
        self._config = config
        self._content_path = str(content_path)

    def execute(self):
        pass

    @property
    def config(self):
        return self._config

    @property
    def args(self):
        return self._args

    @property
    def content_path(self):
        return self._content_path

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
