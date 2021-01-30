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
        'RELEASE': {'help': 'Release name or path to release content'},
    }

    @utils.cached_property
    def jobs(self):
        return (self.imdb_job, self.release_name_job)

    @utils.cached_property
    def release_name_job(self):
        return jobs.release_name.ReleaseNameJob(
            home_directory=utils.fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
        )

    @utils.cached_property
    def imdb_job(self):
        # To be able to fetch the original title, year, etc, we need to prompt
        # for an ID first. IMDb seems to be best.
        imdb_job = jobs.webdb.SearchWebDbJob(
            home_directory=utils.fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            db=utils.webdbs.webdb('imdb'),
        )
        imdb_job.signal.register('output', self.release_name_job.fetch_info)
        return imdb_job
