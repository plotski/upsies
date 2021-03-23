"""
Add torrent file to  BitTorrent client
"""

from .... import jobs, utils
from . import argtypes
from .base import CommandBase


class torrent_add(CommandBase):
    """Add torrent file to BitTorrent client"""

    names = ('torrent-add', 'ta')

    argument_definitions = {
        'CLIENT': {
            'type': argtypes.client,
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
                ignore_cache=self.args.ignore_cache,
                client=utils.btclients.client(
                    name=self.args.CLIENT,
                    **self.config['clients'][self.args.CLIENT],
                ),
                download_path=self.args.download_path,
                enqueue=self.args.TORRENT,
            ),
        )
