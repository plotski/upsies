"""
A command provides a :attr:`~CommandBase.jobs` property that returns a
sequence of :class:`JobBase` objects.  That is the only strict requirement.

Jobs should be created by cached properties that always return the same object.

Jobs can be configured with CLI arguments and a config file. Both are
conveniently provided as :attr:`~CommandBase.args` and
:attr:`~CommandBase.config`.
"""

import abc

from .... import jobs as _jobs
from ....tools import btclient
from ....utils import cache, fs, pipe

import logging  # isort:skip
_log = logging.getLogger(__name__)


class CommandBase(abc.ABC):
    """Base class for all commands"""
    def __init__(self, args, config):
        self._args = args
        self._config = config

    @property
    @abc.abstractmethod
    def jobs(self):
        """
        Sequence of :class:`JobBase` objects

        For convenience, the sequence may also contain `None` instead of an
        optional job.
        """
        pass

    @property
    def jobs_active(self):
        """Same as :attr:`jobs` but with `None` filtered out"""
        return [j for j in self.jobs if j is not None]

    @property
    def args(self):
        """CLI arguments as a :class:`argparse.Namespace` object"""
        return self._args

    @property
    def config(self):
        """Config file options as :class:`config.Config` object"""
        return self._config


class search_db(CommandBase):
    """Search online database like IMDb to get an ID"""
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


class release_name(CommandBase):
    """
    Generate properly formatted release name

    IMDb is searched to get the correct title, year and alternative title if
    applicable.

    Audio and video information is detected with mediainfo.

    Missing required information is highlighted with placeholders,
    e.g. "UNKNOWN_RESOLUTION"
    """
    @cache.property
    def jobs(self):
        return (self.imdb_job, self.release_name_job)

    @cache.property
    def release_name_job(self):
        return _jobs.release_name.ReleaseNameJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
        )

    @cache.property
    def imdb_job(self):
        # To be able to fetch the original title, year, etc, we need to prompt
        # for an ID first. IMDb seems to be best.
        imdb_job = _jobs.search.SearchDbJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            db='imdb',
        )
        imdb_job.on_output(self.release_name_job.fetch_info)
        return imdb_job


class create_torrent(CommandBase):
    """Create torrent file and optionally add it or move it"""
    @cache.property
    def create_torrent_job(self):
        return _jobs.torrent.CreateTorrentJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            tracker_name=self.args.TRACKER,
            tracker_config=self.config['trackers'][self.args.TRACKER],
        )

    @cache.property
    def add_torrent_job(self):
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
            pipe.Pipe(
                sender=self.create_torrent_job,
                receiver=add_job,
            )
            return add_job

    @cache.property
    def copy_torrent_job(self):
        if self.args.copy_to:
            copy_job = _jobs.torrent.CopyTorrentJob(
                homedir=fs.projectdir(self.args.CONTENT),
                ignore_cache=self.args.ignore_cache,
                destination=self.args.copy_to,
            )
            pipe.Pipe(
                sender=self.create_torrent_job,
                receiver=copy_job,
            )
            return copy_job

    @cache.property
    def jobs(self):
        all_jobs = (
            self.create_torrent_job,
            self.add_torrent_job,
            self.copy_torrent_job,
        )
        return tuple(job for job in all_jobs
                     if job is not None)


class add_torrent(CommandBase):
    """Add torrent file to BitTorrent client"""
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


class screenshots(CommandBase):
    """Create screenshots and optionally upload them"""
    @cache.property
    def screenshots_job(self):
        return _jobs.screenshots.ScreenshotsJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            timestamps=self.args.timestamps,
            number=self.args.number,
        )

    @cache.property
    def imghost_job(self):
        image_host = self.args.upload_to
        if image_host:
            imghost_job = _jobs.imghost.ImageHostJob(
                homedir=fs.projectdir(self.args.CONTENT),
                ignore_cache=self.args.ignore_cache,
                image_host=image_host,
                images_total=self.screenshots_job.screenshots_total,
            )
            # Connect ScreenshotsJob's output to ImageHostJob input
            pipe.Pipe(
                sender=self.screenshots_job,
                receiver=imghost_job,
            )
            return imghost_job

    @cache.property
    def jobs(self):
        if self.imghost_job:
            return (
                self.screenshots_job,
                self.imghost_job,
            )
        else:
            return (
                self.screenshots_job,
            )


class upload_images(CommandBase):
    """Upload images to image hosting service"""
    @cache.property
    def jobs(self):
        return (
            _jobs.imghost.ImageHostJob(
                homedir=fs.tmpdir(),
                ignore_cache=self.args.ignore_cache,
                image_host=self.args.IMAGEHOST,
                image_paths=self.args.IMAGE,
            ),
        )


class mediainfo(CommandBase):
    """
    Get mediainfo output

    Directories are recursively searched for the first video file in natural
    order, e.g. "File1.mp4" comes before "File10.mp4".

    Any irrelevant leading parts in the file path are removed from the output.
    """
    @cache.property
    def jobs(self):
        return (
            _jobs.mediainfo.MediainfoJob(
                homedir=fs.projectdir(self.args.CONTENT),
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.CONTENT,
            ),
        )


class submit(CommandBase):
    """
    Collect all required metadata and upload to tracker
    """
    def __new__(cls, args, config):
        from . import _submit
        try:
            module = getattr(_submit, args.TRACKER.lower())
        except AttributeError:
            raise ValueError(f'Unknown tracker: {args.TRACKER}')
        else:
            return module.submit(args=args, config=config)
