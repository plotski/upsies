"""
TODO
"""

from .... import jobs, utils
from .base import CommandBase


class download_location(CommandBase):
    """
    Hard-link existing files as TORRENT expects them and print their location

    Go recursively through all files beneath each LOCATION and collect files
    that match those specified in TORRENT. Hash two pieces of each size-matching
    file and ignore any mismatching files.

    Pick the first LOCATION beneath which a file from TORRENT is found. Create
    hard links to matching files from any LOCATION, replicating the directory
    structure from TORRENT.

    Print the first LOCATION beneath which a file from TORRENT is found. This is
    the download path of the TORRENT.

    If no matching files are found, print the location passed to --default or
    the first LOCATION if there is no --default location.
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
