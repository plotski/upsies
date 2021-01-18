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

    The keys ``announce``, ``source`` and ``exclude`` always exist.
    """

    _defaults = {
        'announce'   : '',
        'source'     : '',
        'exclude'    : [],
        'add-to'     : '',
        'copy-to'    : '',
    }

    defaults = {}
    """Default values"""

    def __new__(cls, config={}):
        combined_defaults = {**cls._defaults, **cls.defaults}
        for k in config:
            if k not in combined_defaults:
                raise TypeError(f'Unknown option: {k!r}')
        obj = super().__new__(cls)
        obj.update(combined_defaults)
        obj.update(config)
        return obj

    # If the config is passed as config={...}, super().__init__() will interpret
    # as a key-value pair that ends up in the config.
    def __init__(cls, *args, **kwargs):
        pass


class TrackerJobsBase(abc.ABC):
    """
    Base class for tracker-specific :class:`jobs <upsies.jobs.base.JobBase>`

    Jobs are instantiated on demand by an instance of this class, which means
    all arguments for all jobs must be given to this class during instantiation.

    Job instances are provided as :func:`~functools.cached_property`, i.e. jobs
    are created only once per session.

    This base class defines general-purpose jobs that can be used by subclasses
    by returning them in their :attr:`.jobs_before_upload` or
    :attr:`.jobs_after_upload` attributes.

    For a description of the arguments see the corresponding properties.
    """

    def __init__(self, *, content_path, tracker, image_host, bittorrent_client,
                 torrent_destination, common_job_args):
        self._content_path = content_path
        self._tracker = tracker
        self._image_host = image_host
        self._bittorrent_client = bittorrent_client
        self._torrent_destination = torrent_destination
        self._common_job_args = common_job_args

    @property
    def content_path(self):
        """Path to the content to generate metadata for"""
        return self._content_path

    @property
    def tracker(self):
        """:class:`~.trackers.base.TrackerBase` subclass"""
        return self._tracker

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

        .. note::

           Jobs returned by this class should have :attr:`~.JobBase.autostart`
           set to False or they will be started along with
           :attr:`.jobs_before_upload`.

        By default, this returns :attr:`.add_torrent_job` and
        :attr:`.copy_torrent_job`.
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
            tracker=self.tracker,
            **self.common_job_args,
        )

    @cached_property
    def add_torrent_job(self):
        """:class:`~.jobs.torrent.AddTorrentJob` instance"""
        if self.bittorrent_client:
            add_torrent_job = _jobs.torrent.AddTorrentJob(
                autostart=False,
                client=self.bittorrent_client,
                download_path=fs.dirname(self.content_path),
                **self.common_job_args,
            )
            # Pass CreateTorrentJob output to AddTorrentJob input.
            self.create_torrent_job.signal.register('output', add_torrent_job.enqueue)
            # Tell AddTorrentJob to finish the current upload and then finish.
            self.create_torrent_job.signal.register('finished', add_torrent_job.finalize)
            return add_torrent_job

    @cached_property
    def copy_torrent_job(self):
        """:class:`~.jobs.torrent.CopyTorrentJob` instance"""
        if self.torrent_destination:
            copy_torrent_job = _jobs.torrent.CopyTorrentJob(
                autostart=False,
                destination=self.torrent_destination,
                **self.common_job_args,
            )
            # Pass CreateTorrentJob output to CopyTorrentJob input.
            self.create_torrent_job.signal.register('output', copy_torrent_job.enqueue)
            # Tell CopyTorrentJob to finish when CreateTorrentJob is done.
            self.create_torrent_job.signal.register('finished', copy_torrent_job.finalize)
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

    screenshots = 2
    """Number many screenshots to make"""

    @cached_property
    def screenshots_job(self):
        """:class:`~.jobs.screenshots.ScreenshotsJob` instance"""
        return _jobs.screenshots.ScreenshotsJob(
            content_path=self.content_path,
            number=self.screenshots,
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
            self.screenshots_job.signal.register('output', imghost_job.enqueue)
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

    :param config: User configuration options for this tracker,
        e.g. authentication details, announce URL, etc
    :type config: :attr:`~.TrackerBase.TrackerConfig` instance
    """

    @property
    @abc.abstractmethod
    def TrackerJobs(self):
        """Subclass of :class:.TrackerJobsBase`"""

    @property
    @abc.abstractmethod
    def TrackerConfig(self):
        """Subclass of :class:.TrackerConfigBase`"""

    def __init__(self, config={}):
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
        """User configuration options from initialization argument"""
        return self._config

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
