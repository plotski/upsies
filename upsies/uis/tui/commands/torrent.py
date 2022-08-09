"""
Commands related to torrent files
"""

import aiobtclientapi

from .... import constants, jobs, trackers, utils
from .base import CommandBase


class torrent_add(CommandBase):
    """Add torrent file to BitTorrent client"""

    names = ('torrent-add', 'ta')

    argument_definitions = {
        'CLIENT': {
            'type': utils.argtypes.client,
            'help': ('Case-insensitive BitTorrent client name\n'
                     'Supported clients: ' + ', '.join(aiobtclientapi.client_names())),
        },
        'TORRENT': {
            'nargs': '+',
            'help': 'Path to torrent file',
        },
        ('--download-path', '-p'): {
            'help': "Parent directory of the torrent's content",
            'metavar': 'DIRECTORY',
        },
    }

    @utils.cached_property
    def jobs(self):
        client_name = self.args.CLIENT
        options = self.get_options('clients', client_name)
        return (
            jobs.torrent.AddTorrentJob(
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                ignore_cache=self.args.ignore_cache,
                client_api=aiobtclientapi.api(
                    name=client_name,
                    url=options['url'],
                    username=options['username'],
                    password=options['password'],
                ),
                download_path=self.args.download_path,
                check_after_add=options['check_after_add'],
                enqueue=self.args.TORRENT,
            ),
        )


class torrent_create(CommandBase):
    """
    Create torrent file and optionally add or copy it

    The piece hashes are cached and re-used if possible. This means the torrent
    is not generated for every tracker again. Note that the torrent is always
    generated if files are excluded on one tracker but not on the other. The
    files in each torrent must be identical.
    """

    names = ('torrent-create', 'tc')

    argument_definitions = {}

    subcommand_name = 'TRACKER'
    subcommands = {
        tracker.name: {
            'description': (
                f'Create a torrent file for {tracker.label} '
                'in the current working directory.'
            ),
            'cli': {
                # Default arguments for all tackers
                **{
                    'CONTENT': {
                        'type': utils.argtypes.content,
                        'help': 'Path to release content',
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
                },
                # Custom arguments defined by tracker for this command
                **tracker.TrackerConfig.argument_definitions.get('torrent-create', {}),
            }
        }
        for tracker in trackers.trackers()
    }

    @utils.cached_property
    def tracker_name(self):
        return self.args.subcommand.lower()

    @property
    def home_directory(self):
        """Create torrent file in current working directory"""
        return '.'

    @utils.cached_property
    def create_torrent_job(self):
        return jobs.torrent.CreateTorrentJob(
            home_directory=self.home_directory,
            cache_directory=self.cache_directory,
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            reuse_torrent_path=(
                tuple(self.args.reuse_torrent)
                + tuple(self.config['config']['torrent-create']['reuse_torrent_paths'])
            ),
            tracker=trackers.tracker(
                name=self.tracker_name,
                options={**self.config['trackers'][self.tracker_name],
                         **vars(self.args)},
            ),
            exclude_files=(
                tuple(self.args.exclude_files)
                + tuple(self.args.exclude_files_regex)
            ),
        )

    @utils.cached_property
    def add_torrent_job(self):
        if self.args.add_to:
            client_name = self.args.add_to
            config = self.config['clients'][client_name]
            add_torrent_job = jobs.torrent.AddTorrentJob(
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                ignore_cache=self.args.ignore_cache,
                client_api=aiobtclientapi.api(
                    name=client_name,
                    url=config['url'],
                    username=config['username'],
                    password=config['password'],
                ),
                download_path=utils.fs.dirname(self.args.CONTENT),
                check_after_add=config['check_after_add'],
            )
            # Pass CreateTorrentJob output to AddTorrentJob input.
            self.create_torrent_job.signal.register('output', add_torrent_job.enqueue)
            # Finish AddTorrentJob when CreateTorrentJob is finished. The
            # torrent will be enqueued and AddTorrentJob will finish after
            # adding the enqueued torrent.
            self.create_torrent_job.signal.register('finished', lambda _: add_torrent_job.finalize())
            return add_torrent_job

    @utils.cached_property
    def copy_torrent_job(self):
        if self.args.copy_to:
            copy_torrent_job = jobs.torrent.CopyTorrentJob(
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                ignore_cache=self.args.ignore_cache,
                destination=self.args.copy_to,
            )
            # Pass CreateTorrentJob output to CopyTorrentJob input.
            self.create_torrent_job.signal.register('output', copy_torrent_job.enqueue)
            # Tell CopyTorrentJob to finish when CreateTorrentJob is done.
            self.create_torrent_job.signal.register('finished', lambda _: copy_torrent_job.finalize())
            return copy_torrent_job

    @utils.cached_property
    def jobs(self):
        return (
            self.create_torrent_job,
            self.add_torrent_job,
            self.copy_torrent_job,
        )
