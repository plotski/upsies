from ..... import jobs as _jobs
from .....utils import cache, fs
from ._base import SubmitCommandBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class submit(SubmitCommandBase):
    @cache.property
    def jobs(self):
        return (
            self.create_torrent_job,
            self.mediainfo_job,
            self.tvmaze_job,
            self.submission_job,
            self.add_torrent_job,
            self.copy_torrent_job,
        )

    @cache.property
    def required_jobs(self):
        return (
            self.create_torrent_job,
            self.mediainfo_job,
            self.tvmaze_job,
        )

    @cache.property
    def tvmaze_job(self):
        return _jobs.search.SearchDbJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            db='tvmaze',
        )

    @cache.property
    def mediainfo_job(self):
        return _jobs.mediainfo.MediainfoJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            quiet=True,
        )
