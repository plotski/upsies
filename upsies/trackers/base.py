"""
Abstract base class for tracker APIs
"""

import abc

from .. import jobs as _jobs
from ..utils import cached_property, fs, webdbs

import logging  # isort:skip
_log = logging.getLogger(__name__)


class TrackerConfigBase(dict):
    """
    Dictionary with default values that are defined by the subclass
    """

    defaults = {}
    """Default values"""

    def __new__(cls, **kwargs):
        for k in kwargs:
            if k not in cls.defaults:
                raise TypeError(f'Unknown option: {k!r}')
        return {**cls.defaults, **kwargs}


class TrackerJobsBase(abc.ABC):
    """
    Base class for tracker-specific :class:`jobs <upsies.jobs.base.JobBase>`

    Every argument any job of any subclass needs must be given as an argument to
    ths class when it is instantiated.

    Job instances are provided as :func:`~functools.cached_property` attributes
    that return :class:`~.jobs.base.JobBase` instances. That means jobs are
    created on demand and only once per session.

    This base class defines general-purpose jobs that can be used by subclasses
    by returning them in their :attr:`.jobs_before_upload` or
    :attr:`.jobs_after_upload` attributes.

    For a description of the arguments see their corresponding properties.
    """

    def __init__(self, *, content_path, tracker_name, tracker_config,
                 image_host, bittorrent_client, torrent_destination,
                 common_job_args):
        self._tracker_name = tracker_name
        self._tracker_config = tracker_config
        self._content_path = content_path
        self._image_host = image_host
        self._bittorrent_client = bittorrent_client
        self._torrent_destination = torrent_destination
        self._common_job_args = common_job_args

    @property
    def tracker_name(self):
        """Lower-case tracker name abbreviation"""
        return self._tracker_name

    @property
    def tracker_config(self):
        """
        User configuration as a :class:`dict`

        This contains values users can configure via configuration files, CLI
        arguments, UI widgets, etc.
        """
        return self._tracker_config

    @property
    def content_path(self):
        """Path to the content to generate metadata for"""
        return self._content_path

    @property
    def image_host(self):
        """:class:`~.utils.imghosts.base.ImageHostBase` instance or `None`"""
        return self._image_host

    @property
    def bittorrent_client(self):
        """:class:`~.utils.imghosts.base.ImageHostBase` instance or `None`"""
        return self._bittorrent_client

    @property
    def torrent_destination(self):
        """Path to copy the generated torrent file to or `None`"""
        return self._torrent_destination

    @property
    def common_job_args(self):
        """Keyword arguments as a dictionary that are passed to all jobs"""
        return self._common_job_args

    @property
    @abc.abstractmethod
    def jobs_before_upload(self):
        """
        Sequence of jobs that need to finish before :meth:`~.TrackerBase.upload` can
        be called
        """

    @cached_property
    def jobs_after_upload(self):
        """
        Sequence of jobs that are started after :meth:`~.TrackerBase.upload`
        finished

        :attr:`.add_torrent_job` and :attr:`.copy_torrent_job` by default.
        """
        return (
            self.add_torrent_job,
            self.copy_torrent_job,
        )

    @cached_property
    def create_torrent_job(self):
        """:class:`~.jobs.torrent.CreateTorrentJob` instance"""
        return _jobs.torrent.CreateTorrentJob(
            content_path=self.content_path,
            tracker_name=self.tracker_name,
            tracker_config=self.tracker_config,
            **self.common_job_args,
        )

    @cached_property
    def add_torrent_job(self):
        """:class:`~.jobs.torrent.AddTorrentJob` instance"""
        if self.bittorrent_client:
            add_torrent_job = _jobs.torrent.AddTorrentJob(
                client=self.bittorrent_client,
                download_path=fs.dirname(self.content_path),
                **self.common_job_args,
            )
            # Pass CreateTorrentJob output to AddTorrentJob input.
            self.create_torrent_job.signal.register('output', add_torrent_job.add)
            # Tell AddTorrentJob to finish the current upload and then finish.
            self.create_torrent_job.signal.register('finished', add_torrent_job.finalize)
            return add_torrent_job

    @cached_property
    def copy_torrent_job(self):
        """:class:`~.jobs.torrent.CopyTorrentJob` instance"""
        if self.torrent_destination:
            copy_torrent_job = _jobs.torrent.CopyTorrentJob(
                destination=self.torrent_destination,
                **self.common_job_args,
            )
            # Pass CreateTorrentJob output to CopyTorrentJob input.
            self.create_torrent_job.signal.register('output', copy_torrent_job.copy)
            # Tell CopyTorrentJob to finish when CreateTorrentJob is done.
            self.create_torrent_job.signal.register('finished', copy_torrent_job.finish)
            return copy_torrent_job

    @cached_property
    def release_name_job(self):
        """:class:`~.jobs.release_name.ReleaseNameJob` instance"""
        return _jobs.release_name.ReleaseNameJob(
            content_path=self.content_path,
            **self.common_job_args,
        )

    @cached_property
    def imdb_job(self):
        """:class:`~.jobs.webdb.SearchWebDbJob` instance"""
        imdb_job = _jobs.webdb.SearchWebDbJob(
            content_path=self.content_path,
            db=webdbs.webdb('imdb'),
            **self.common_job_args,
        )
        # Update release name with IMDb data
        imdb_job.signal.register('output', self.release_name_job.fetch_info)
        return imdb_job

    @cached_property
    def tmdb_job(self):
        """:class:`~.jobs.webdb.SearchWebDbJob` instance"""
        return _jobs.webdb.SearchWebDbJob(
            content_path=self.content_path,
            db=webdbs.webdb('tmdb'),
            **self.common_job_args,
        )

    @cached_property
    def tvmaze_job(self):
        """:class:`~.jobs.webdb.SearchWebDbJob` instance"""
        return _jobs.webdb.SearchWebDbJob(
            content_path=self.content_path,
            db=webdbs.webdb('tvmaze'),
            **self.common_job_args,
        )

    @cached_property
    def screenshots_job(self):
        """:class:`~.jobs.screenshots.ScreenshotsJob` instance"""
        return _jobs.screenshots.ScreenshotsJob(
            content_path=self.content_path,
            **self.common_job_args,
        )

    @cached_property
    def upload_screenshots_job(self):
        """:class:`~.jobs.imghost.ImageHostJob` instance"""
        if self.image_host:
            imghost_job = _jobs.imghost.ImageHostJob(
                imghost=self.image_host,
                **self.common_job_args,
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
        """:class:`~.jobs.mediainfo.MediainfoJob` instance"""
        return _jobs.mediainfo.MediainfoJob(
            content_path=self.content_path,
            **self.common_job_args,
        )


class TrackerBase(abc.ABC):
    """
    Base class for tracker-specific operations, e.g. uploading

    :param config: Any keyword arguments are used for user configuration,
        e.g. authentication credentials
    """

    def __init__(self, **config):
        self._config = config

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
        """User configuration from :meth:`__init__` keyword arguments as dictionary"""
        return self._config

    @property
    @abc.abstractmethod
    def TrackerJobs(self):
        """Subclass of :class:.TrackerJobsBase`"""

    @property
    @abc.abstractmethod
    def TrackerConfig(self):
        """Subclass of :class:.TrackerConfigBase`"""

    @abc.abstractmethod
    async def login(self):
        """Start user session"""

    @abc.abstractmethod
    async def logout(self):
        """End user session"""

    @abc.abstractmethod
    async def upload(self, metadata):
        """
        Upload torrent and other metadata

        :param dict metadata: Mapping of :attr:`.JobBase.name` to
            :attr:`.JobBase.output` attributes for each job in
            :attr:`.jobs_before_upload`

            .. note:: Job output is always an immutable sequence.
        """
