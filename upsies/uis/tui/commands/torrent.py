"""
Commands related to torrent files
"""

from .... import jobs, trackers, utils
from .base import CommandBase


class torrent_add(CommandBase):
    """Add torrent file to BitTorrent client"""

    names = ('torrent-add', 'ta')

    argument_definitions = {
        'CLIENT': {
            'type': utils.argtypes.client,
            'help': ('Case-insensitive BitTorrent client name\n'
                     'Supported clients: ' + ', '.join(utils.btclients.client_names())),
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
        return (
            jobs.torrent.AddTorrentJob(
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                ignore_cache=self.args.ignore_cache,
                client=utils.btclients.client(
                    name=self.args.CLIENT,
                    config=self.config['clients'][self.args.CLIENT],
                ),
                download_path=self.args.download_path,
                enqueue=self.args.TORRENT,
            ),
        )


class torrent_create(CommandBase):
    """Create torrent file and optionally add or copy it"""

    names = ('torrent-create', 'tc')

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
    def tracker_name(self):
        return self.args.subcommand.lower()

    @utils.cached_property
    def create_torrent_job(self):
        return jobs.torrent.CreateTorrentJob(
            home_directory=self.home_directory,
            cache_directory=self.cache_directory,
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            tracker=trackers.tracker(
                name=self.tracker_name,
                options={**self.config['trackers'][self.tracker_name],
                         **vars(self.args)},
            ),
        )

    @utils.cached_property
    def add_torrent_job(self):
        if self.args.add_to:
            add_torrent_job = jobs.torrent.AddTorrentJob(
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                ignore_cache=self.args.ignore_cache,
                client=utils.btclients.client(
                    name=self.args.add_to,
                    config=self.config['clients'][self.args.add_to],
                ),
                download_path=utils.fs.dirname(self.args.CONTENT),
            )
            # Pass CreateTorrentJob output to AddTorrentJob input.
            self.create_torrent_job.signal.register('output', add_torrent_job.enqueue)
            # Tell AddTorrentJob to finish the current upload and then finish.
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
