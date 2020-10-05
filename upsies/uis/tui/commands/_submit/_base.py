import abc

from ..... import jobs as _jobs
from .....utils import cache, fs
from .. import CommandBase, create_torrent

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmitCommandBase(CommandBase, abc.ABC):
    """
    Base class for all commands that submit to a tracker

    It provides jobs for creating the torrent and submitting it to the
    tracker.

    Picking a DB ID, creating screenshots, etc must be added by the child class
    by overriding the :attr:`jobs` property.
    """

    @cache.property
    @abc.abstractmethod
    def jobs(self):
        pass

    @cache.property
    @abc.abstractmethod
    def required_jobs(self):
        """
        Dictionary of jobs that must finish before :attr:`submission_job` can start

        Keys can be anything hashable and are only used by the
        :class:`SubmissionJob` instance.
        """
        pass

    @cache.property
    def _create_torrent_cmd(self):
        return create_torrent(
            args=self.args,
            config=self.config,
        )

    @cache.property
    def create_torrent_job(self):
        return self._create_torrent_cmd.create_torrent_job

    @cache.property
    def add_torrent_job(self):
        return self._create_torrent_cmd.add_torrent_job

    @cache.property
    def copy_torrent_job(self):
        return self._create_torrent_cmd.copy_torrent_job

    @cache.property
    def submission_job(self):
        try:
            module = getattr(_jobs.submit, self.args.TRACKER.lower())
        except AttributeError:
            raise RuntimeError(f'Unknown tracker: {self.args.TRACKER}')
        else:
            SubmissionJob = module.SubmissionJob

        return SubmissionJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            tracker_config=self.config['trackers'][self.args.TRACKER],
            required_jobs=self.required_jobs,
        )
