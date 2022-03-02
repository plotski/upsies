"""
Find files from a torrent and create links if necessary
"""

from .... import jobs, utils
from .base import CommandBase


class download_location(CommandBase):
    """
    Hard-link existing files as TORRENT expects them and print their location

    1. Find files from TORRENT in the file system.

       1.1 Beneath each LOCATION, find a file with the same size as the one
           specified in TORRENT.

       1.2 Keep the file with the most similar name.

       1.3 Hash two pieces to confirm matching file content.

    2. If necessary, create hard links beneath the first LOCATION a matching
       file was found and print that LOCATION. This is the download path you
       should pass to your client when adding TORRENT.

       If no matching files are found, print the location passed to --default or
       the first LOCATION if there is no --default.
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
