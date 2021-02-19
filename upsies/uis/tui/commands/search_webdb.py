"""
Search online database like IMDb to get an ID
"""

from .... import jobs, utils
from . import argtypes
from .base import CommandBase


class search_webdb(CommandBase):
    """
    Search online database like IMDb to get an ID

    Pressing ``Enter`` searches for the current query. Pressing ``Enter`` again without
    changing the query selects the focused search result.

    The focused search result can be opened in the default web browser with
    ``Alt-Enter``.
    """

    names = ('id',)

    argument_definitions = {
        'DB': {
            'type': argtypes.webdb,
            'help': ('Case-insensitive database name\n'
                     'Supported databases: ' + ', '.join(utils.webdbs.webdb_names())),
        },
        'RELEASE': {
            'type': argtypes.release,
            'help': 'Release name or path to release content',
        },
    }

    @utils.cached_property
    def jobs(self):
        return (
            jobs.webdb.SearchWebDbJob(
                home_directory=utils.fs.projectdir(self.args.RELEASE),
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.RELEASE,
                db=utils.webdbs.webdb(self.args.DB),
            ),
        )
