from ... import jobs as _jobs
from ...tools import btclient
from ...utils import cache, fs

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubcommandBase:
    def __init__(self, args, config):
        self._args = args
        self._config = config

    @property
    def args(self):
        return self._args

    @property
    def config(self):
        return self._config


class search_db(SubcommandBase):
    @cache.property
    def jobs(self):
        return (
            _jobs.search.SearchDbJob(
                homedir=fs.projectdir(self.args.CONTENT),
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.CONTENT,
                db=self.args.DB,
            ),
        )


class release_name(SubcommandBase):
    @cache.property
    def jobs(self):
        # To be able to fetch the correct title, original title, year, etc, we
        # need to prompt for an ID first. IMDb seems to be best.
        imdb_job = _jobs.search.SearchDbJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            db='imdb',
        )
        rn_job = _jobs.release_name.ReleaseNameJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
        )
        imdb_job.on_output(rn_job.fetch_info)
        return (imdb_job, rn_job)


class create_torrent(SubcommandBase):
    @cache.property
    def _create_job(self):
        return _jobs.torrent.CreateTorrentJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            tracker_name=self.args.TRACKER,
            tracker_config=self.config['trackers'][self.args.TRACKER],
        )

    @cache.property
    def _add_job(self):
        if self.args.add_to:
            add_job = _jobs.torrent.AddTorrentJob(
                homedir=fs.projectdir(self.args.CONTENT),
                ignore_cache=self.args.ignore_cache,
                client=btclient.client(
                    name=self.args.add_to,
                    **self.config['clients'][self.args.add_to],
                ),
                download_path=fs.dirname(self.args.CONTENT),
            )
            _jobs.Pipe(
                sender=self._create_job,
                receiver=add_job,
            )
            return add_job

    # TODO: Add --copy-to job

    @cache.property
    def jobs(self):
        return tuple(
            job for job in (self._create_job, self._add_job)
            if job is not None
        )


class add_torrent(SubcommandBase):
    @cache.property
    def jobs(self):
        return (
            _jobs.torrent.AddTorrentJob(
                homedir=fs.tmpdir(),
                ignore_cache=self.args.ignore_cache,
                client=btclient.client(
                    name=self.args.CLIENT,
                    **self.config['clients'][self.args.CLIENT],
                ),
                download_path=self.args.download_path,
                torrents=self.args.TORRENT,
            ),
        )


class screenshots(SubcommandBase):
    @cache.property
    def _screenshots_job(self):
        return _jobs.screenshots.ScreenshotsJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            timestamps=self.args.timestamps,
            number=self.args.number,
        )

    @cache.property
    def _imghost_job(self):
        image_host = self.args.upload_to
        if image_host:
            imghost_job = _jobs.imghost.ImageHostJob(
                homedir=fs.projectdir(self.args.path),
                ignore_cache=self.args.ignore_cache,
                image_host=image_host,
                images_total=self._screenshots_job.screenshots_total,
            )
            # Connect ScreenshotsJob's output to ImageHostJob input
            _jobs.Pipe(
                sender=self._screenshots_job,
                receiver=imghost_job,
            )
            return imghost_job

    @cache.property
    def jobs(self):
        if self._imghost_job:
            return (
                self._screenshots_job,
                self._imghost_job,
            )
        else:
            return (
                self._screenshots_job,
            )


class upload_images(SubcommandBase):
    @cache.property
    def jobs(self):
        return (
            _jobs.imghost.ImageHostJob(
                homedir=fs.tmpdir(),
                ignore_cache=self.args.ignore_cache,
                image_host=self.args.IMAGEHOST,
                image_paths=self.args.CONTENT,
            ),
        )


class mediainfo(SubcommandBase):
    @cache.property
    def jobs(self):
        return (
            _jobs.mediainfo.MediainfoJob(
                homedir=fs.projectdir(self.args.CONTENT),
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.CONTENT,
            ),
        )


class submit(SubcommandBase):
    @cache.property
    def jobs(self):
        try:
            tracker = getattr(_jobs.submit, self.args.TRACKER)
        except AttributeError:
            raise ValueError(f'Unknown tracker: {self.args.TRACKER}')

        _log.debug('Tracker: %r', self.args.TRACKER)
        _log.debug('Submission class: %r', tracker.SubmissionJob)
        sub = tracker.SubmissionJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            args=self.args,
            config=_get_tracker_section(self.config, self.args.TRACKER),
        )
        _log.debug('Tracker jobs: %r', sub.jobs)
        return sub.jobs
