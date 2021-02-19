"""
Generate all required metadata and upload to tracker
"""

from .... import constants, jobs, trackers, utils
from . import argtypes
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
                    'type': argtypes.content,
                    'help': 'Path to release content',
                },
                ('--add-to', '-a'): {
                    'type': argtypes.client,
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
            home_directory=utils.fs.projectdir(self.args.CONTENT),
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
    def tracker_config(self):
        """Dictionary of :attr:`tracker_name` section in trackers configuration file"""
        return self.config['trackers'][self.tracker_name]

    @utils.cached_property
    def tracker(self):
        """
        :class:`~.trackers.base.TrackerBase` instance from one of the submodules of
        :mod:`.trackers`
        """
        return trackers.tracker(
            name=self.tracker_name,
            config=self.tracker_config,
            cli_args=self.args,
        )

    @utils.cached_property
    def tracker_jobs(self):
        """
        :class:`~.trackers.base.TrackerJobsBase` instance from one of the submodules
        of :mod:`.trackers`
        """
        return self.tracker.TrackerJobs(
            content_path=self.args.CONTENT,
            tracker=self.tracker,
            image_host=self._get_imghost(),
            bittorrent_client=self._get_btclient(),
            torrent_destination=self._get_torrent_destination(),
            common_job_args={
                'home_directory': utils.fs.projectdir(self.args.CONTENT),
                'ignore_cache': self.args.ignore_cache,
            },
            cli_args=self.args,
        )

    def _get_imghost(self):
        imghost_name = self.tracker_config.get('image_host', None)
        if imghost_name:
            return utils.imghosts.imghost(
                name=imghost_name,
                **self.config['imghosts'][imghost_name],
            )

    def _get_btclient(self):
        btclient_name = (getattr(self.args, 'add_to', None)
                         or self.tracker_config.get('add-to', None)
                         or None)
        if btclient_name:
            return utils.btclients.client(
                name=btclient_name,
                **self.config['clients'][btclient_name],
            )

    def _get_torrent_destination(self):
        return (getattr(self.args, 'copy_to', None)
                or self.tracker_config.get('copy-to', None)
                or None)
