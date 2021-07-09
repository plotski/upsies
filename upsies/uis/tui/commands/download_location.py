"""
TODO
"""

from .... import jobs, utils
from .base import CommandBase


class download_location(CommandBase):
    """
    Hardlink existing files as TORRENT expects them

    TODO: Explain exactly how this works.
    """

    names = ('download-location', 'dloc')

    argument_definitions = {
        'TORRENT': {
            'help': 'Path to torrent file',
        },
        'LOCATION': {
            'nargs': '+',
            'help': 'Potential path of existing files in TORRENT',
        },
        ('--default',): {
            'help': 'Default location if no existing files are found',
        },
    }

    @utils.cached_property
    def jobs(self):
        return (
            jobs.download_location.DownloadLocationJob(
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                torrent=self.args.TORRENT,
                locations=self.args.LOCATION,
                default=self.args.default,
            ),
        )
