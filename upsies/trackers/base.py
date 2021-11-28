"""
Abstract base class for tracker APIs
"""

import abc
import builtins

from .. import jobs
from ..utils import (btclients, cached_property, configfiles, fs, release,
                     signal, types, webdbs)

import logging  # isort:skip
_log = logging.getLogger(__name__)


class TrackerConfigBase(dict):
    """
    Dictionary with default values that are defined by the subclass

    The keys ``announce``, ``source`` and ``exclude`` always exist.
    """

    _defaults = {
        'source': configfiles.config_value(
            value='',
            description='Value of the "source" field in generated torrents.',
        ),
        'exclude': configfiles.config_value(
            value=[],
            description='List of regular expressions. Matching files are excluded from generated torrents.',
        ),
        'add_to': configfiles.config_value(
            value=types.Choice(
                value='',
                empty_ok=True,
                options=(client.name for client in btclients.clients()),
            ),
            description=('BitTorrent client to add torrent to after submission.'),
        ),
        'copy_to': configfiles.config_value(
            value='',
            description='Directory path to copy torrent to after submission.',
        ),
    }

    defaults = {}
    """Default values"""

    argument_definitions = {}
    """CLI argument definitions (see :attr:`.CommandBase.argument_definitions`)"""

    def __new__(cls, config={}):
        # Merge generic and tracker-specific defaults
        combined_defaults = cls._merge(cls._defaults, cls.defaults)

        # Check user-given config for unknown options
        for k in config:
            if k not in combined_defaults:
                raise TypeError(f'Unknown option: {k!r}')

        # Merge user-given config with defaults
        obj = super().__new__(cls)
        obj.update(cls._merge(combined_defaults, config))
        return obj

    @staticmethod
    def _merge(a, b):
        # Copy a
        combined = {}
        combined.update(a)

        # Update a with values from b
        for k, v in b.items():
            if k in combined:
                # Ensure same value type from a
                cls = type(combined[k])
                combined[k] = cls(v)
            else:
                # Append new value
                combined[k] = v

        return combined

    # If the config is passed as config={...}, super().__init__() will interpret
    # as a key-value pair that ends up in the config.
    def __init__(cls, *args, **kwargs):
        pass


class TrackerJobsBase(abc.ABC):
    """
    Base class for tracker-specific :class:`jobs <upsies.jobs.base.JobBase>`

    This base class defines general-purpose jobs that can be used by subclasses
    by returning them in their :attr:`jobs_before_upload` or
    :attr:`jobs_after_upload` attributes. It also provides all objects that are
    needed by any one of those jobs.

    Job instances are provided as :func:`~functools.cached_property`, i.e. jobs
    are created only once per session.

    Subclasses that need to run background tasks (e.g. with
    :func:`asyncio.ensure_future`) should attach a callback to them with
    :meth:`~.asyncio.Task.add_done_callback` that catches expected exceptions
    and pass them to :meth:`warn`, :meth:`error` or :meth:`exception`.

    For a description of the arguments see the corresponding properties.
    """

    def __init__(self, *, content_path, tracker,
                 reuse_torrent_path=None, torrent_destination=None,
                 exclude_files=(), options=None, image_host=None,
                 bittorrent_client=None, common_job_args=None):
        self._content_path = content_path
        self._reuse_torrent_path = reuse_torrent_path
        self._tracker = tracker
        self._image_host = image_host
        self._bittorrent_client = bittorrent_client
        self._torrent_destination = torrent_destination
        self._exclude_files = exclude_files
        self._common_job_args = common_job_args or {}
        self._options = options or {}
        self._signal = signal.Signal('warning', 'error', 'exception')
        self._background_tasks = []

    @property
    def content_path(self):
        """
        Content path to generate metadata for

        This is the same object that was passed as a initialization argument.
        """
        return self._content_path

    @property
    def tracker(self):
        """
        :class:`~.trackers.base.TrackerBase` subclass

        This is the same object that was passed as a initialization argument.
        """
        return self._tracker

    @property
    def reuse_torrent_path(self):
        """
        Path to an existing torrent file that matches :attr:`content_path`

        See :func:`.torrent.create`.
        """
        return self._reuse_torrent_path

    @property
    def torrent_destination(self):
        """
        Where to copy the generated torrent file to or `None`

        This is the same object that was passed as a initialization argument.
        """
        return self._torrent_destination

    @property
    def exclude_files(self):
        """
        Sequence of glob and regular expression patterns to exclude from the
        generated torrent

        See the ``exclude_files`` argument of
        :meth:`.CreateTorrentJob.initialize`.
        """
        return self._exclude_files

    @property
    def options(self):
        """
        Configuration options provided by the user

        This is the same object that was passed as a initialization argument.
        """
        return self._options

    @property
    def image_host(self):
        """
        :class:`~.base.ImageHostBase` instance or `None`

        This is the same object that was passed as a initialization argument.
        """
        return self._image_host

    @property
    def bittorrent_client(self):
        """
        :class:`~.base.ClientApiBase` instance or `None`

        This is the same object that was passed as a initialization argument.
        """
        return self._bittorrent_client

    @property
    def common_job_args(self):
        """
        Keyword arguments that are passed to all jobs or empty `dict`

        This is the same object that was passed as a initialization argument.
        """
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

        .. note:: Jobs returned by this class should have
                  :attr:`~.JobBase.autostart` set to `False` or they will be
                  started before submission is attempted.

        By default, this returns :attr:`add_torrent_job` and
        :attr:`copy_torrent_job`.
        """
        return (
            self.add_torrent_job,
            self.copy_torrent_job,
        )

    @property
    def submission_ok(self):
        """
        Whether the created metadata should be submitted

        The base class implementation simply returns `True` if all
        :attr:`jobs_before_upload` have an :attr:`~.base.JobBase.exit_code` of
        ``0`` or a falsy :attr:`~.base.JobBase.is_enabled` value.

        Subclasses should always call the parent class implementation to ensure
        all metadata was created successfully.
        """
        enabled_jobs_before_upload = tuple(
            job for job in self.jobs_before_upload
            if job and job.is_enabled
        )
        return (
            bool(enabled_jobs_before_upload)
            and all(job.exit_code == 0
                    for job in enabled_jobs_before_upload)
        )

    @property
    def signal(self):
        """
        :class:`~.signal.Signal` instance with the signals ``warning``, ``error``
        and ``exception``
        """
        return self._signal

    def warn(self, warning):
        """
        Emit ``warning`` signal (see :attr:`signal`)

        Emit a warning for any non-critical issue that the user can choose to
        ignore or fix.
        """
        self.signal.emit('warning', warning)

    def error(self, error):
        """
        Emit ``error`` signal (see :attr:`signal`)

        Emit an error for any critical but expected issue that can't be
        recovered from (e.g. I/O error).
        """
        self.signal.emit('error', error)

    def exception(self, exception):
        """
        Emit ``exception`` signal (see :attr:`signal`)

        Emit an exception for any critical and unexpected issue that should be
        reported as a bug.
        """
        self.signal.emit('exception', exception)

    @cached_property
    def imdb(self):
        """:class:`~.webdbs.imdb.ImdbApi` instance"""
        return webdbs.webdb('imdb')

    @cached_property
    def tmdb(self):
        """:class:`~.webdbs.tmdb.TmdbApi` instance"""
        return webdbs.webdb('tmdb')

    @cached_property
    def tvmaze(self):
        """:class:`~.webdbs.tvmaze.TvmazeApi` instance"""
        return webdbs.webdb('tvmaze')

    def get_job_name(self, name):
        """
        Return job name that is unique for this tracker

        It's important for tracker jobs to have unique names to avoid re-using
        cached output from another tracker's job with the same name.

        Standard jobs chose their names so that cached output will be re-used by
        other trackers if possible. This function is mainly for unique and
        custom jobs that are only used for one tracker but might share the same
        name with other trackers.
        """
        prefix = f'{self.tracker.name}-'
        if name.startswith(prefix):
            return name
        else:
            return f'{prefix}{name}'

    @cached_property
    def create_torrent_job(self):
        """:class:`~.jobs.torrent.CreateTorrentJob` instance"""
        return jobs.torrent.CreateTorrentJob(
            content_path=self.content_path,
            reuse_torrent_path=self.reuse_torrent_path,
            tracker=self.tracker,
            exclude_files=self._exclude_files,
            **self.common_job_args,
        )

    @cached_property
    def add_torrent_job(self):
        """:class:`~.jobs.torrent.AddTorrentJob` instance"""
        if self.bittorrent_client and self.create_torrent_job:
            add_torrent_job = jobs.torrent.AddTorrentJob(
                autostart=False,
                client=self.bittorrent_client,
                download_path=fs.dirname(self.content_path),
                **self.common_job_args,
            )
            # Pass CreateTorrentJob output to AddTorrentJob input.
            self.create_torrent_job.signal.register('output', add_torrent_job.enqueue)
            # Tell AddTorrentJob to finish the current upload and then finish.
            self.create_torrent_job.signal.register('finished', self.finalize_add_torrent_job)
            return add_torrent_job

    def finalize_add_torrent_job(self, _):
        self.add_torrent_job.finalize()

    @cached_property
    def copy_torrent_job(self):
        """:class:`~.jobs.torrent.CopyTorrentJob` instance"""
        if self.torrent_destination and self.create_torrent_job:
            copy_torrent_job = jobs.torrent.CopyTorrentJob(
                autostart=False,
                destination=self.torrent_destination,
                **self.common_job_args,
            )
            # Pass CreateTorrentJob output to CopyTorrentJob input.
            self.create_torrent_job.signal.register('output', copy_torrent_job.enqueue)
            # Tell CopyTorrentJob to finish when CreateTorrentJob is done.
            self.create_torrent_job.signal.register('finished', self.finalize_copy_torrent_job)
            return copy_torrent_job

    def finalize_copy_torrent_job(self, _):
        self.copy_torrent_job.finalize()

    @cached_property
    def release_name(self):
        """
        :class:`~.release.ReleaseName` instance with
        :attr:`release_name_translation` applied
        """
        return release.ReleaseName(
            path=self.content_path,
            translate=self.release_name_translation,
        )

    release_name_translation = {}
    """See ``translate`` argument of :attr:`~.utils.release.ReleaseName`"""

    @cached_property
    def release_name_job(self):
        """
        :class:`~.jobs.dialog.TextFieldJob` instance with text set to
        :attr:`release_name`

        The text is automatically updated when :attr:`imdb_job` sends an ID.
        """
        job = jobs.dialog.TextFieldJob(
            name=self.get_job_name('release-name'),
            label='Release Name',
            text=str(self.release_name),
            **self.common_job_args,
        )
        # Automatically update release_name with user-confirmed release name
        job.signal.register('output', self.release_name.set_release_info)
        return job

    def _update_release_name(self, imdb_id):
        self.release_name_job.add_task(
            self.release_name_job.fetch_text(
                coro=self.release_name.fetch_info(imdb_id=imdb_id),
                error_is_fatal=False,
            ),
        )

    @cached_property
    def imdb_job(self):
        """:class:`~.jobs.webdb.WebDbSearchJob` instance"""
        imdb_job = jobs.webdb.WebDbSearchJob(
            query=self.content_path,
            db=self.imdb,
            **self.common_job_args,
        )
        # Update release name with IMDb data
        imdb_job.signal.register('output', self._update_release_name)
        return imdb_job

    @cached_property
    def tmdb_job(self):
        """:class:`~.jobs.webdb.WebDbSearchJob` instance"""
        return jobs.webdb.WebDbSearchJob(
            query=self.content_path,
            db=self.tmdb,
            **self.common_job_args,
        )

    @cached_property
    def tvmaze_job(self):
        """:class:`~.jobs.webdb.WebDbSearchJob` instance"""
        return jobs.webdb.WebDbSearchJob(
            query=self.content_path,
            db=self.tvmaze,
            **self.common_job_args,
        )

    @cached_property
    def screenshots_job(self):
        """
        :class:`~.jobs.screenshots.ScreenshotsJob` instance

        The number of screenshots to make is taken from the "--screenshots" CLI
        argument, if present and non-falsy, and defaults to :attr:`screenshots`.
        """
        return jobs.screenshots.ScreenshotsJob(
            content_path=self.content_path,
            count=self.options.get('screenshots'),
            **self.common_job_args,
        )

    image_host_config = {}
    """
    Dictionary that maps an image hosting service :attr:`~.ImageHostBase.name`
    to :attr:`~.ImageHostBase.default_config` values

    ``common`` is a special image host whose values are always applied.

    Example:

    >>> image_host_config = {
    ...     # Always generate 300p thumbnails
    ...     'common': {'thumb_width': 300},
    ...     # If "myhost" is used, use this API key, but only for this tracker
    ...     'myhost': {'apikey': 'd34db33f'},
    ... }
    """

    @cached_property
    def upload_screenshots_job(self):
        """:class:`~.jobs.imghost.ImageHostJob` instance"""
        if self.image_host and self.screenshots_job:
            imghost_job = jobs.imghost.ImageHostJob(
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
            self.screenshots_job.signal.register('finished', self.finalize_upload_screenshots_job)
            return imghost_job

    def finalize_upload_screenshots_job(self, _):
        self.upload_screenshots_job.finalize()

    @cached_property
    def mediainfo_job(self):
        """:class:`~.jobs.mediainfo.MediainfoJob` instance"""
        return jobs.mediainfo.MediainfoJob(
            content_path=self.content_path,
            **self.common_job_args,
        )

    @cached_property
    def scene_check_job(self):
        """:class:`~.jobs.scene.SceneCheckJob` instance"""
        return jobs.scene.SceneCheckJob(
            content_path=self.content_path,
            **self.common_job_args,
        )

    def make_choice_job(self, name, label, options, condition=None,
                        callbacks=None, autodetected=None, autofinish=False):
        """
        Return :class:`~.jobs.dialog.ChoiceJob` instance

        :param name: See :class:`~.jobs.dialog.ChoiceJob`
        :param label: See :class:`~.jobs.dialog.ChoiceJob`
        :param autodetected: Autodetected choice

        :param options: Sequence of :class:`dict`-like objects with the
            following keys:

            - ``label``: User-facing value

            - ``value``: Internal value that is made available via the
              :attr:`~.dialog.ChoiceJob.choice` attribute of the returned object

            - ``match`` (Optional): Callable that gets `autodetected`; if its return value
              is truthy, this option is autofocused

            - ``regex`` (Optional): Regular expression; if this matches `autodetected`,
              this option is autofocused

        :param condition: See :attr:`~.base.JobBase.condition`
        :param callbacks: See :attr:`~.base.JobBase`
        :param bool autofinish: Whether to choose the autodetected value with no
            user-interaction
        """
        def is_autodetected(option):
            regex = option.get('regex')
            match = option.get('match')
            if autodetected:
                if regex and regex.search(str(autodetected)):
                    return True
                elif match and match(autodetected):
                    return True
            return False

        focused = None
        choices = []
        for option in options:
            if not focused and is_autodetected(option):
                choices.append((f'{option["label"]} (autodetected)', option['value']))
                focused = choices[-1]
                autofinish = autofinish and True
            else:
                choices.append((option['label'], option['value']))

        job = jobs.dialog.ChoiceJob(
            name=self.get_job_name(name),
            label=label,
            condition=condition,
            callbacks=callbacks or {},
            choices=choices,
            focused=focused,
            **self.common_job_args,
        )
        if autofinish and focused:
            job.choice = focused
        return job

    def get_job_output(self, job, slice=None):
        """
        Helper method for getting output from job

        `job` must be finished.

        :param job: :class:`~.jobs.base.JobBase` instance
        :param slice: :class:`int` to get a specific item from `job`'s output,
            `None` to return all output as a list or a :class:`slice` object

        :raise RuntimeError: if `job` is not finished or getting `slice` from
            :attr:`~.base.JobBase.output` raises an :class:`IndexError`
        :return: :class:`list` or :class:`str`
        """
        if not job.is_finished:
            raise RuntimeError(f'Unfinished job: {job.name}')
        if slice is None:
            slice = builtins.slice(None, None)
        try:
            return job.output[slice]
        except IndexError:
            raise RuntimeError(f'Job finished with insufficient output: {job.name}: {job.output}')

    def get_job_attribute(self, job, attribute):
        """
        Helper method for getting an attribute from job

        `job` must be finished.

        :raise RuntimeError: if `job` is not finished
        :raise AttributeError: if `attribute` is not an attribute of `job`
        """
        if not job.is_finished:
            raise RuntimeError(f'Unfinished job: {job.name}')
        else:
            return getattr(job, attribute)


class TrackerBase(abc.ABC):
    """
    Base class for tracker-specific operations, e.g. uploading

    :param options: User configuration options for this tracker,
        e.g. authentication details, announce URL, etc
    :type options: :class:`dict`-like
    """

    @property
    @abc.abstractmethod
    def TrackerJobs(self):
        """Subclass of :class:`TrackerJobsBase`"""

    @property
    @abc.abstractmethod
    def TrackerConfig(self):
        """Subclass of :class:`TrackerConfigBase`"""

    def __init__(self, options=None):
        self._options = options or {}
        self._signal = signal.Signal('warning', 'error', 'exception')

    @property
    @abc.abstractmethod
    def name(self):
        """Lower-case tracker name abbreviation for internal use"""

    @property
    @abc.abstractmethod
    def label(self):
        """User-facing tracker name abbreviation"""

    @property
    def options(self):
        """
        Configuration options provided by the user

        This is the :class:`dict`-like object from the initialization argument
        of the same name.
        """
        return self._options

    @abc.abstractmethod
    async def login(self):
        """Start user session"""

    @abc.abstractmethod
    async def logout(self):
        """End user session"""

    @property
    @abc.abstractmethod
    def is_logged_in(self):
        """Whether a user session is active"""

    @abc.abstractmethod
    async def get_announce_url(self):
        """Get announce URL from tracker website"""

    @abc.abstractmethod
    async def upload(self, tracker_jobs):
        """
        Upload torrent and other metadata from jobs

        :param TrackerJobsBase tracker_jobs: :attr:`TrackerJobs` instance
        """

    @property
    def signal(self):
        """
        :class:`~.signal.Signal` instance with the signals ``warning``, ``error``
        and ``exception``
        """
        return self._signal

    def warn(self, warning):
        """
        Emit ``warning`` signal (see :attr:`signal`)

        Emit a warning for any non-critical issue that the user can choose to
        ignore or fix.
        """
        self.signal.emit('warning', warning)

    def error(self, error):
        """
        Emit ``error`` signal (see :attr:`signal`)

        Emit an error for any critical but expected issue that can't be
        recovered from (e.g. I/O error).
        """
        self.signal.emit('error', error)

    def exception(self, exception):
        """
        Emit ``exception`` signal (see :attr:`signal`)

        Emit an exception for any critical and unexpected issue that should be
        reported as a bug.
        """
        self.signal.emit('exception', exception)
