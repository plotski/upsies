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
    def release_name(self):
        return utils.release.ReleaseName(self.args.RELEASE)

    @utils.cached_property
    def release_name_job(self):
        return jobs.dialog.TextFieldJob(
            name='release-name',
            label='Release Name',
            text=str(self.release_name),
            home_directory=self.home_directory,
            cache_directory=self.cache_directory,
            ignore_cache=self.args.ignore_cache,
        )

    def _update_release_name(self, imdb_id):
        self.release_name_job.add_task(
            self.release_name_job.fetch_text(
                coro=self.release_name.fetch_info(imdb_id),
                error_is_fatal=False,
            ),
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
            callbacks={'output': self._update_release_name},
        )
