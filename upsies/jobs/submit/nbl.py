from ...tools import mediainfo
from ...utils import cache, fs
from .. import search, torrent
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmissionJob(_base.SubmissionJobBase):
    @cache.property
    def torrent_job(self):
        return torrent.CreateTorrentJob(
            homedir=fs.projectdir(self.content_path, self.trackername),
            ignore_cache=False,
            content_path=self.content_path,
            exclude_regexs=self.config['exclude'],
            trackername=self.trackername,
            announce_url=self.config['announce'],
            source='NBL',
        )

    @property
    def torrent_file(self):
        if self.torrent_job.output:
            return self.torrent_job.output[0]

    @cache.property
    def search_job(self):
        return search.SearchDbJob(
            homedir=fs.projectdir(self.content_path, self.trackername),
            ignore_cache=False,
            content_path=self.content_path,
            db='tvmaze',
        )

    @property
    def dbid(self):
        if self.search_job.output:
            return self.search_job.output[0]

    @cache.property
    def jobs(self):
        return (
            self.torrent_job,
            self.search_job,
            self,
        )

    async def submit(self):
        _log.debug('Submitting to NBL')
        _log.debug('TVmaze ID: %r', self.dbid)
        _log.debug('Torrent: %r', self.torrent_file)
        _log.debug('Mediainfo: %r', mediainfo.as_string(self.content_path))
        self.send('<url to submitteded torrent>')
