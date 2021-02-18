"""
Add torrent file to  BitTorrent client
"""

from .... import constants, jobs, utils
from . import argtypes
from .base import CommandBase


class add_torrent(CommandBase):
    """Add torrent file to BitTorrent client"""

    names = ('add-torrent', 'at')

    argument_definitions = {
        'CLIENT': {
            'type': argtypes.client,
            'help': ('Case-insensitive BitTorrent client name\n'
                     'Supported clients: ' + ', '.join(constants.BTCLIENT_NAMES)),
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
                ignore_cache=self.args.ignore_cache,
                client=utils.btclients.client(
                    name=self.args.CLIENT,
                    **self.config['clients'][self.args.CLIENT],
                ),
                download_path=self.args.download_path,
                enqueue=self.args.TORRENT,
            ),
        )
