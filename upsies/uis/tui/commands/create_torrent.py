"""
Create torrent file and optionally add or copy it
"""

from .... import constants, jobs, trackers, utils
from . import argtypes
from .base import CommandBase


class create_torrent(CommandBase):
    """Create torrent file and optionally add or copy it"""

    names = ('create-torrent', 'ct')

    argument_definitions = {
        'TRACKER': {
            'type': utils.types.tracker,
            'help': ('Case-insensitive tracker name.\n'
                     'Supported trackers: ' + ', '.join(constants.TRACKER_NAMES)),
        },
        'CONTENT': {
            'type': argtypes.content,
            'help': 'Path to release content',
        },
        ('--add-to', '-a'): {
            'type': utils.types.client,
            'metavar': 'CLIENT',
            'help': ('Case-insensitive BitTorrent client name\n'
                     'Supported clients: ' + ', '.join(constants.BTCLIENT_NAMES)),
        },
        ('--copy-to', '-c'): {
            'metavar': 'PATH',
            'help': 'Copy the created torrent to PATH (file or directory)',
        },
    }

    @utils.cached_property
    def create_torrent_job(self):
        return jobs.torrent.CreateTorrentJob(
            home_directory=utils.fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            tracker=trackers.tracker(
                name=self.args.TRACKER.lower(),
                config=self.config['trackers'][self.args.TRACKER.lower()],
            ),
        )

    @utils.cached_property
    def add_torrent_job(self):
        if self.args.add_to:
            add_torrent_job = jobs.torrent.AddTorrentJob(
                home_directory=utils.fs.projectdir(self.args.CONTENT),
                ignore_cache=self.args.ignore_cache,
                client=utils.btclients.client(
                    name=self.args.add_to,
                    **self.config['clients'][self.args.add_to],
                ),
                download_path=utils.fs.dirname(self.args.CONTENT),
            )
            # Pass CreateTorrentJob output to AddTorrentJob input.
            self.create_torrent_job.signal.register('output', add_torrent_job.enqueue)
            # Tell AddTorrentJob to finish the current upload and then finish.
            self.create_torrent_job.signal.register('finished', add_torrent_job.finalize)
            return add_torrent_job

    @utils.cached_property
    def copy_torrent_job(self):
        if self.args.copy_to:
            copy_torrent_job = jobs.torrent.CopyTorrentJob(
                home_directory=utils.fs.projectdir(self.args.CONTENT),
                ignore_cache=self.args.ignore_cache,
                destination=self.args.copy_to,
            )
            # Pass CreateTorrentJob output to CopyTorrentJob input.
            self.create_torrent_job.signal.register('output', copy_torrent_job.enqueue)
            # Tell CopyTorrentJob to finish when CreateTorrentJob is done.
            self.create_torrent_job.signal.register('finished', copy_torrent_job.finalize)
            return copy_torrent_job

    @utils.cached_property
    def jobs(self):
        return (
            self.create_torrent_job,
            self.add_torrent_job,
            self.copy_torrent_job,
        )
