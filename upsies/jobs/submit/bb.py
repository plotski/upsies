from ...tools import guessit, mediainfo
from ...utils import cache, fs
from .. import screenshots, search, torrent
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
            trackername=self.trackername,
            announce_url=self.announce_url,
            source='bB',
        )

    @property
    def torrent_file(self):
        if self.torrent_job.output:
            return self.torrent_job.output[0]

    @cache.property
    def screenshots_job(self):
        return screenshots.ScreenshotsJob(
            homedir=fs.projectdir(self.content_path, self.trackername),
            ignore_cache=False,
            content_path=self.content_path,
            number=2,
            # upload_to='imgbox',
        )

    @property
    def screenshot_files(self):
        if self.screenshots_job.output:
            return self.screenshots_job.output[0]

    @cache.property
    def search_job(self):
        guess = guessit.guessit(self.content_path)
        if guess['type'] == 'movie':
            db = 'imdb'
        else:
            db = 'tvmaze'
        return search.SearchDbJob(
            homedir=fs.projectdir(self.content_path, self.trackername),
            ignore_cache=False,
            content_path=self.content_path,
            db=db,
        )

    @property
    def dbid(self):
        if self.search_job.output:
            return self.search_job.output[0]

    @cache.property
    def jobs(self):
        return (
            self.torrent_job,
            self.screenshots_job,
            self.search_job,
            self,
        )

    async def submit(self):
        _log.debug('Submitting to Bb')
        _log.debug('Torrent: %r', self.torrent_file)
        _log.debug('Screenshots: %r', self.screenshot_files)
        _log.debug('ID: %r', self.dbid)
        _log.debug('Mediainfo: %r', mediainfo.as_string(self.content_path))
        self.send('<url to submitteded torrent>')
