"""
Find files from a torrent and create links if necessary
"""

from .... import jobs, utils
from .base import CommandBase


class download_location(CommandBase):
    """
    Hard-link existing files as TORRENT expects them and print their location

    Recursively find all files beneath each LOCATION that have the same size as
    those specified in TORRENT and hash two pieces of each size-matching file to
    be extra sure.

    For each file in TORRENT, hard-link the first match to the file path
    specified in TORRENT, prepending LOCATION to the relative path from the
    torrent.

    Print the first LOCATION beneath which a file from TORRENT is found. This is
    the download path of the TORRENT you should pass to your client when adding
    the torrent.

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
