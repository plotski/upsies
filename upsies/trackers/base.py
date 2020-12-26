"""
Abstract base class for tracker APIs
"""

import abc
import types

from .. import jobs as _jobs
from ..utils import cached_property, fs, webdbs

import logging  # isort:skip
_log = logging.getLogger(__name__)


class TrackerBase(abc.ABC):
    """
    Base class for tracker-specific operations, e.g. uploading

    :param config: Dictionary of the relevant tracker's section in the trackers
        configuration file
    :param job_input: Any additional keyword arguments are provided as a
        :class:`~.types.SimpleNamespace` object via the :attr:`job_input`
        property. The idea is to use that information to instantiate the jobs
        that generate the metadata for submission.
    """

    def __init__(self, config, **job_input):
        self._config = config
        self._job_input = types.SimpleNamespace(**job_input)

    @property
    @abc.abstractmethod
    def name(self):
        """Lower-case tracker name abbreviation for internal use"""

    @property
    @abc.abstractmethod
    def label(self):
        """User-facing tracker name abbreviation"""

    @property
    def config(self):
        """Configuration file section for this tracker as a dictionary"""
        return self._config

    @property
    def job_input(self):
        """Keyword arguments from instantiation as :class:`~.types.SimpleNamespace`"""
        return self._job_input

    @property
    @abc.abstractmethod
    def jobs_before_upload(self):
        """Sequence of jobs that need to finish before :meth:`upload` can be called"""

    @cached_property
    def jobs_after_upload(self):
        """Sequence of jobs that are started after :meth:`upload` finished"""
        return (
            self.add_torrent_job,
            self.copy_torrent_job,
        )

    @cached_property
    def create_torrent_job(self):
        return _jobs.torrent.CreateTorrentJob(
            homedir=self.job_input.homedir,
            ignore_cache=self.job_input.ignore_cache,
            content_path=self.job_input.content_path,
            tracker_name=self.name,
            tracker_config=self.config,
        )

    @cached_property
    def add_torrent_job(self):
        if self.job_input.add_to_client:
            add_torrent_job = _jobs.torrent.AddTorrentJob(
                homedir=self.job_input.homedir,
                ignore_cache=self.job_input.ignore_cache,
                client=self.job_input.add_to_client,
                download_path=fs.dirname(self.job_input.content_path),
            )
            # Pass CreateTorrentJob output to AddTorrentJob input.
            self.create_torrent_job.signal.register('output', add_torrent_job.add)
            # Tell AddTorrentJob to finish the current upload and then finish.
            self.create_torrent_job.signal.register('finished', add_torrent_job.finalize)
            return add_torrent_job

    @cached_property
    def copy_torrent_job(self):
        if self.job_input.torrent_destination:
            copy_torrent_job = _jobs.torrent.CopyTorrentJob(
                homedir=self.job_input.homedir,
                ignore_cache=self.job_input.ignore_cache,
                destination=self.job_input.torrent_destination,
            )
            # Pass CreateTorrentJob output to CopyTorrentJob input.
            self.create_torrent_job.signal.register('output', copy_torrent_job.copy)
            # Tell CopyTorrentJob to finish when CreateTorrentJob is done.
            self.create_torrent_job.signal.register('finished', copy_torrent_job.finish)
            return copy_torrent_job

    @cached_property
    def release_name_job(self):
        return _jobs.release_name.ReleaseNameJob(
            homedir=self.job_input.homedir,
            ignore_cache=self.job_input.ignore_cache,
            content_path=self.job_input.content_path,
        )

    @cached_property
    def imdb_job(self):
        imdb_job = _jobs.webdb.SearchWebDbJob(
            homedir=self.job_input.homedir,
            ignore_cache=self.job_input.ignore_cache,
            content_path=self.job_input.content_path,
            db=webdbs.webdb('imdb'),
        )
        # Update release name with IMDb data
        imdb_job.signal.register('output', self.release_name_job.fetch_info)
        return imdb_job

    @cached_property
    def tmdb_job(self):
        return _jobs.webdb.SearchWebDbJob(
            homedir=self.job_input.homedir,
            ignore_cache=self.job_input.ignore_cache,
            content_path=self.job_input.content_path,
            db=webdbs.webdb('tmdb'),
        )

    @cached_property
    def tvmaze_job(self):
        return _jobs.webdb.SearchWebDbJob(
            homedir=self.job_input.homedir,
            ignore_cache=self.job_input.ignore_cache,
            content_path=self.job_input.content_path,
            db=webdbs.webdb('tvmaze'),
        )

    @cached_property
    def screenshots_job(self):
        return _jobs.screenshots.ScreenshotsJob(
            homedir=self.job_input.homedir,
            ignore_cache=self.job_input.ignore_cache,
            content_path=self.job_input.content_path,
        )

    @cached_property
    def upload_screenshots_job(self):
        if self.job_input.image_host:
            imghost_job = _jobs.imghost.ImageHostJob(
                homedir=self.job_input.homedir,
                ignore_cache=self.job_input.ignore_cache,
                imghost=self.job_input.image_host,
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

    @cached_property
    def mediainfo_job(self):
        return _jobs.mediainfo.MediainfoJob(
            homedir=self.job_input.homedir,
            ignore_cache=self.job_input.ignore_cache,
            content_path=self.job_input.content_path,
        )

    @abc.abstractmethod
    async def login(self):
        """
        Start user session

        Authentication credentials should be taken from
        :attr:`~.TrackerBase.config`.
        """

    @abc.abstractmethod
    async def logout(self):
        """Stop user session"""

    @abc.abstractmethod
    async def upload(self, metadata):
        """
        Upload torrent and other metadata

        :param dict metadata: Map :attr:`~.TrackerBase.name` to
            :attr:`~.JobBase.output` attributes for each job in
            :attr:`~.jobs_before_upload`

            .. note:: Job output is always an immutable sequence.
        """


class TrackerConfigBase(dict):
    """
    Dictionary with default values that can be defined on the subclass
    """

    defaults = {}
    """Default values"""

    def __new__(cls, **kwargs):
        for k in kwargs:
            if k not in cls.defaults:
                raise TypeError(f'Unknown option: {k!r}')
        return {**cls.defaults, **kwargs}
