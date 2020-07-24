import abc

from .. import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmissionBase(_base.JobBase, abc.ABC):
    name = 'submission'
    label = 'Submission'

    @property
    def trackername(self):
        cls = type(self)
        if cls.__module__:
            return cls.__module__.split('.')[-1]

    def initialize(self, content_path, announce_url):
        self._content_path = str(content_path)
        self._announce_url = announce_url

    def execute(self):
        pass

    @property
    def content_path(self):
        return self._content_path

    @property
    def announce_url(self):
        return self._announce_url

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
        if not self.is_finished:
            await self.submit()
