"""
Generate all required metadata and upload to tracker
"""

from .... import jobs, trackers, utils
from .base import CommandBase


class submit(CommandBase):
    """Generate all required metadata and upload to tracker"""

    names = ('submit',)

    argument_definitions = {}

    subcommands = {
        tracker.name: {
            # Default arguments for all tackers
            **{
                'CONTENT': {
                    'type': utils.argtypes.content,
                    'help': 'Path to release content',
                },
                ('--add-to', '-a'): {
                    'type': utils.argtypes.client,
                    'metavar': 'CLIENT',
                    'help': ('Case-insensitive BitTorrent client name\n'
                             'Supported clients: ' + ', '.join(utils.btclients.client_names())),
                },
                ('--copy-to', '-c'): {
                    'metavar': 'PATH',
                    'help': 'Copy the created torrent to PATH (file or directory)',
                },
            },
            # Custom arguments defined by tracker
            **tracker.argument_definitions,
        }
        for tracker in trackers.trackers()
    }

    @utils.cached_property
    def jobs(self):
        submit_job = jobs.submit.SubmitJob(
            home_directory=self.home_directory,
            cache_directory=self.cache_directory,
            ignore_cache=self.args.ignore_cache,
            tracker=self.tracker,
            tracker_jobs=self.tracker_jobs,
        )
        return (
            tuple(self.tracker_jobs.jobs_before_upload)
            + (submit_job,)
            + tuple(self.tracker_jobs.jobs_after_upload)
        )

    @utils.cached_property
    def tracker_name(self):
        """Lower-case abbreviation of tracker name"""
        return self.args.subcommand.lower()

    @utils.cached_property
    def tracker_options(self):
        """
        :attr:`tracker_name` section in trackers configuration file combined with
        CLI arguments where CLI arguments take precedence unless their value is
        `None`
        """
        config = self.config['trackers'][self.tracker_name]
        cli_args = vars(self.args)
        options = {}
        options.update(config)
        for k, v in cli_args.items():
            if v is not None:
                options[k] = v
        return options

    @utils.cached_property
    def tracker(self):
        """
        :class:`~.trackers.base.TrackerBase` instance from one of the submodules of
        :mod:`.trackers`
        """
        return trackers.tracker(
            name=self.tracker_name,
            options=self.tracker_options,
        )

    @utils.cached_property
    def tracker_jobs(self):
        """
        :class:`~.trackers.base.TrackerJobsBase` instance from one of the submodules
        of :mod:`.trackers`
        """
        return self.tracker.TrackerJobs(
            options=self.tracker_options,
            content_path=self.args.CONTENT,
            tracker=self.tracker,
            image_host=self._get_imghost(),
            bittorrent_client=self._get_btclient(),
            torrent_destination=self._get_torrent_destination(),
            common_job_args={
                'home_directory': self.home_directory,
                'cache_directory': self.cache_directory,
                'ignore_cache': self.args.ignore_cache,
            },
        )

    def _get_imghost(self):
        imghost_name = self.tracker_options.get('image_host', None)
        if imghost_name:
            # Apply tracker-specific image host configuration
            imghost_config = self.config['imghosts'][imghost_name].copy()
            imghost_config.update(self.tracker.TrackerJobs.image_host_config.get(imghost_name, {}))
            return utils.imghosts.imghost(
                name=imghost_name,
                config=imghost_config,
            )

    def _get_btclient(self):
        btclient_name = (getattr(self.args, 'add_to', None)
                         or self.tracker_options.get('add-to', None)
                         or None)
        if btclient_name:
            return utils.btclients.client(
                name=btclient_name,
                config=self.config['clients'][btclient_name],
            )

    def _get_torrent_destination(self):
        return (getattr(self.args, 'copy_to', None)
                or self.tracker_options.get('copy-to', None)
                or None)
