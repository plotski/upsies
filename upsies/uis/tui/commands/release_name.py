"""
Generate properly formatted release name
"""

from .... import jobs, utils
from .base import CommandBase


class release_name(CommandBase):
    """
    Generate properly formatted release name

    IMDb is searched to get the correct title, year and alternative title if
    applicable.

    Audio and video information is detected with mediainfo.

    Missing required information is highlighted with placeholders,
    e.g. "UNKNOWN_RESOLUTION"
    """

    names = ('release-name', 'rn')

    argument_definitions = {
        'RELEASE': {
            'type': utils.argtypes.release,
            'help': 'Release name or path to release content',
        },
    }

    @utils.cached_property
    def jobs(self):
        return (self.imdb_job, self.release_name_job)

    @utils.cached_property
    def release_name_job(self):
        return jobs.release_name.ReleaseNameJob(
            home_directory=self.home_directory,
            cache_directory=self.cache_directory,
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.RELEASE,
        )

    @utils.cached_property
    def imdb_job(self):
        # To be able to fetch the original title, year, etc, we need to ask for
        # an ID first. IMDb seems to be best.
        return jobs.webdb.WebDbSearchJob(
            home_directory=self.home_directory,
            cache_directory=self.cache_directory,
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.RELEASE,
            db=utils.webdbs.webdb('imdb'),
            callbacks={'output': self.release_name_job.fetch_info},
        )
