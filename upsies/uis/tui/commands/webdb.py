"""
Search online database like IMDb to get an ID
"""

from .... import jobs, utils
from .base import CommandBase


class webdb_search(CommandBase):
    """
    Search online database like IMDb to get an ID

    Pressing ``Enter`` searches for the current query. Pressing ``Enter`` again
    without changing the query selects the focused search result.

    The focused search result can be opened in the default web browser with
    ``Alt-Enter``.

    Search results can be narrowed down with the following parameters:

      - year:YYYY
        Only return results with a specific release year.

      - type:series|movie
        Only return movies or series.

      - id:ID
        Search for a specific, known ID.
    """

    names = ('id',)

    argument_definitions = {
        'DB': {
            'type': utils.argtypes.webdb,
            'help': ('Case-insensitive database name\n'
                     'Supported databases: ' + ', '.join(utils.webdbs.webdb_names())),
        },
        'RELEASE': {
            'type': utils.argtypes.release,
            'help': 'Release name or path to release content',
        },
    }

    @utils.cached_property
    def jobs(self):
        return (
            jobs.webdb.WebDbSearchJob(
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.RELEASE,
                db=utils.webdbs.webdb(self.args.DB),
            ),
        )
