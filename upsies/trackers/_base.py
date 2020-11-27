import abc
import types

from .. import jobs as _jobs
from ..utils import cache, fs

import logging  # isort:skip
_log = logging.getLogger(__name__)


class TrackerBase(abc.ABC):
    """
    Base class for tracker-specific operations, e.g. uploading

    :param config: Dictionary of the relevant tracker's section in the trackers
        configuration file
    :param info: Any additional keyword arguments are provided as attributes of
        the :attr:`info` property. These can be used to instantiate the jobs
        that generate the metadata for submission.
    """

    def __init__(self, config, **info):
        self._config = config
        self._info = types.SimpleNamespace(**info)

    @property
    @abc.abstractmethod
    def name(self):
        """Tracker name abbreviation"""
        pass

    @property
    def config(self):
        """Configuration file section for this tracker as a dictionary"""
        return self._config

    @property
    def info(self):
        return self._info

    @property
    @abc.abstractmethod
    def jobs_before_upload(self):
        """Sequence of jobs that need to finish before :meth:`upload` can be called"""
        pass

    @cache.property
    def jobs_after_upload(self):
        """Sequence of jobs that are started :meth:`upload` can be called"""
        return (
            self.add_torrent_job,
            self.copy_torrent_job,
        )

    @cache.property
    def create_torrent_job(self):
        return _jobs.torrent.CreateTorrentJob(
            homedir=self.info.homedir,
            ignore_cache=self.info.ignore_cache,
            content_path=self.info.content_path,
            tracker_name=self.info.tracker_name,
            tracker_config=self.config,
        )

    @cache.property
    def add_torrent_job(self):
        if self.info.add_to_client:
            add_torrent_job = _jobs.torrent.AddTorrentJob(
                homedir=self.info.homedir,
                ignore_cache=self.info.ignore_cache,
                client=self.info.add_to_client,
                download_path=fs.dirname(self.info.content_path),
            )
            # Pass CreateTorrentJob output to AddTorrentJob input.
            self.create_torrent_job.signal.register('output', add_torrent_job.add)
            # Tell AddTorrentJob to finish the current upload and then finish.
            self.create_torrent_job.signal.register('finished', add_torrent_job.finalize)
            return add_torrent_job

    @cache.property
    def copy_torrent_job(self):
        if self.info.torrent_destination:
            copy_torrent_job = _jobs.torrent.CopyTorrentJob(
                homedir=self.info.homedir,
                ignore_cache=self.info.ignore_cache,
                destination=self.info.torrent_destination,
            )
            # Pass CreateTorrentJob output to CopyTorrentJob input.
            self.create_torrent_job.signal.register('output', copy_torrent_job.copy)
            # Tell CopyTorrentJob to finish when CreateTorrentJob is done.
            self.create_torrent_job.signal.register('finished', copy_torrent_job.finish)
            return copy_torrent_job

    @cache.property
    def release_name_job(self):
        return _jobs.release_name.ReleaseNameJob(
            homedir=self.info.homedir,
            ignore_cache=self.info.ignore_cache,
            content_path=self.info.content_path,
        )

    @cache.property
    def imdb_job(self):
        imdb_job = _jobs.search.SearchDbJob(
            homedir=self.info.homedir,
            ignore_cache=self.info.ignore_cache,
            content_path=self.info.content_path,
            db='imdb',
        )
        # Update release name with IMDb data
        imdb_job.signal.register('output', self.release_name_job.fetch_info)
        return imdb_job

    @cache.property
    def tmdb_job(self):
        return _jobs.search.SearchDbJob(
            homedir=self.info.homedir,
            ignore_cache=self.info.ignore_cache,
            content_path=self.info.content_path,
            db='tmdb',
        )

    @cache.property
    def tvmaze_job(self):
        return _jobs.search.SearchDbJob(
            homedir=self.info.homedir,
            ignore_cache=self.info.ignore_cache,
            content_path=self.info.content_path,
            db='tvmaze',
        )

    @cache.property
    def screenshots_job(self):
        return _jobs.screenshots.ScreenshotsJob(
            homedir=self.info.homedir,
            ignore_cache=self.info.ignore_cache,
            content_path=self.info.content_path,
            # TODO: Add --number and --timestamps arguments
        )

    @cache.property
    def upload_screenshots_job(self):
        if self.info.image_host:
            imghost_job = _jobs.imghost.ImageHostJob(
                homedir=self.info.homedir,
                ignore_cache=self.info.ignore_cache,
                imghost=self.info.image_host,
            )
            # Timestamps are calculated in a subprocess, we have to wait for
            # that until we can set the number of expected screenhots.
            self.screenshots_job.signal.register(
                'timestamps',
                lambda timestamps: imghost_job.set_images_total(len(timestamps)),
            )
            # Pass ScreenshotsJob's output to ImageHostJob input.
            self.screenshots_job.signal.register('output', imghost_job.upload)
            # Tell imghost_job to finish the current upload and then finish.
            self.screenshots_job.signal.register('finished', imghost_job.finalize)
            return imghost_job

    @cache.property
    def mediainfo_job(self):
        return _jobs.mediainfo.MediainfoJob(
            homedir=self.info.homedir,
            ignore_cache=self.info.ignore_cache,
            content_path=self.info.content_path,
        )

    @abc.abstractmethod
    async def login(self):
        """
        Start user session

        Authentication credentials should be taken from :attr:`config`.
        """
        pass

    @abc.abstractmethod
    async def logout(self):
        """Stop user session"""
        pass

    @abc.abstractmethod
    async def upload(self, metadata):
        """
        Upload torrent and other metadata

        :param dict metadata: Map of job names to job output

            .. note: Job output is always an immutable sequence.
        """
        pass
