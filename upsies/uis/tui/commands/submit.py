"""
Generate all required metadata and upload to tracker
"""

import aiobtclientapi

from .... import __project_name__, constants, jobs, trackers, utils
from . import base


class submit(base.CommandBase):
    """Generate all required metadata and upload to TRACKER"""

    names = ('submit',)

    argument_definitions = {}

    subcommand_name = 'TRACKER'
    subcommands = {
        tracker.name: {
            'description': (
                f'Generate all required metadata and upload it to {tracker.label}.\n'
                '\n'
                f'For step-by-step instructions run this command:\n'
                '\n'
                f'    $ {__project_name__} submit {tracker.name} --howto-setup\n'
            ),
            'cli': {
                # Default arguments for all tackers
                **{
                    'CONTENT': {
                        'type': utils.argtypes.content,
                        'help': 'Path to release content',
                    },
                    ('--is-scene',): {
                        'type': utils.argtypes.is_scene,
                        'default': None,
                        'help': ('Whether this is a scene release (usually autodetected)\n'
                                 'Valid values: '
                                 + ', '.join(
                                     f'{true}/{false}'
                                     for true, false in zip(utils.types.Bool.truthy, utils.types.Bool.falsy)
                                 )),
                    },
                    ('--exclude-files', '--ef'): {
                        'nargs': '+',
                        'metavar': 'PATTERN',
                        'help': ('Glob pattern to exclude from torrent '
                                 '(matched case-sensitively against path in torrent)'),
                        'default': (),
                    },
                    ('--exclude-files-regex', '--efr'): {
                        'nargs': '+',
                        'metavar': 'PATTERN',
                        'help': ('Regular expression to exclude from torrent '
                                 '(matched case-sensitively against path in torrent)'),
                        'type': utils.argtypes.regex,
                        'default': (),
                    },
                    ('--reuse-torrent', '-t'): {
                        'nargs': '+',
                        'metavar': 'TORRENT',
                        'help': ('Use hashed pieces from TORRENT instead of generating '
                                 'them again or getting them from '
                                 f'{utils.fs.tildify_path(constants.GENERIC_TORRENTS_DIRPATH)}.\n'
                                 'TORRENT may also be a directory, which is searched recursively '
                                 'for a matching *.torrent file.\n'
                                 "NOTE: This option is ignored if TORRENT doesn't match properly."),
                        'type': utils.argtypes.existing_path,
                        'default': (),
                    },
                    ('--add-to', '-a'): {
                        'type': utils.argtypes.client,
                        'metavar': 'CLIENT',
                        'help': ('Case-insensitive BitTorrent client name\n'
                                 'Supported clients: ' + ', '.join(aiobtclientapi.client_names())),
                    },
                    ('--copy-to', '-c'): {
                        'metavar': 'PATH',
                        'help': 'Copy the created torrent to PATH (file or directory)',
                    },
                    ('--howto-setup',): {
                        'action': base.PrintText(text_getter=tracker.generate_setup_howto),
                        'nargs': 0,
                        'help': 'Show detailed instructions on how to do your first upload',
                    },
                },
                # Custom arguments defined by tracker for this command
                **tracker.TrackerConfig.argument_definitions.get('submit', {}),
            },
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
        return self.get_options('trackers', self.tracker_name)

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
            reuse_torrent_path=(
                tuple(self.args.reuse_torrent)
                + tuple(self.config['config']['torrent-create']['reuse_torrent_paths'])
            ),
            tracker=self.tracker,
            image_host=self._get_imghost(),
            bittorrent_client=self._get_btclient(),
            torrent_destination=self._get_torrent_destination(),
            check_after_add=self._get_check_after_add(),
            exclude_files=(
                tuple(self.args.exclude_files)
                + tuple(self.args.exclude_files_regex)
            ),
            common_job_args={
                'home_directory': self.home_directory,
                'cache_directory': self.cache_directory,
                'ignore_cache': self.args.ignore_cache,
            },
        )

    def _get_imghost(self):
        imghost_name = self.tracker_options.get('image_host', None)
        if imghost_name:
            # Get global image host options
            options = self.config['imghosts'][imghost_name].copy()

            # Apply tracker-specific options that are common for all image hosts
            options.update(self.tracker.TrackerJobs.image_host_config.get('common', {}))

            # Apply tracker-specific options for the used image host
            options.update(self.tracker.TrackerJobs.image_host_config.get(imghost_name, {}))

            return utils.imghosts.imghost(
                name=imghost_name,
                options=options,
            )

    def _get_btclient_name(self):
        return (getattr(self.args, 'add_to', None)
                or self.tracker_options.get('add_to', None)
                or None)

    def _get_btclient(self):
        btclient_name = self._get_btclient_name()
        if btclient_name:
            options = self.get_options('clients', btclient_name)
            return aiobtclientapi.api(
                name=btclient_name,
                url=options['url'],
                username=options['username'],
                password=options['password'],
            )

    def _get_torrent_destination(self):
        return (getattr(self.args, 'copy_to', None)
                or self.tracker_options.get('copy_to', None)
                or None)

    def _get_check_after_add(self):
        btclient_config = self.config['clients'].get(self._get_btclient_name())
        if btclient_config:
            return btclient_config['check_after_add']
