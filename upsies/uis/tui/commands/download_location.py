"""
Find files from a torrent and create links if necessary
"""

from .... import jobs, utils
from .base import CommandBase


class download_location(CommandBase):
    """
    Find files from TORRENT, create links if necessary, and print their location

    1. Find files from TORRENT in the file system.

       1.1 Beneath each LOCATION, find a file with the same size as the one
           specified in TORRENT.

       1.2 If there are multiple size matches, pick the file with the most
           similar name to the one specified in TORRENT.

       1.3 Hash some pieces to confirm the file content is what TORRENT expects.

    2. Pick the first LOCATION where a matching file was found. This is the
       download directory that should be used when adding TORRENT to a
       BitTorrent client.

    3. Make sure every matching file exists beneath the download directory with
       the same relative path as in TORRENT. Try to create a hard link and
       default to a symbolic link if this fails because the link source and
       target are on different file systems.

    4. Print the download directory (see 2.).

       If no matching files are found, print the location passed to --default or
       the first LOCATION if there is no --default.

       This is the only output.
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
