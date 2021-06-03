"""
Searching for and verifying scene release
"""

from .... import jobs, utils
from .base import CommandBase


class scene_search(CommandBase):
    """Search for scene release name"""

    names = ('scene-search', 'scs')

    argument_definitions = {
        'RELEASE': {
            'type': utils.argtypes.release,
            'help': 'Release name or path to release content',
        },
    }

    @utils.cached_property
    def jobs(self):
        return (
            jobs.scene.SceneSearchJob(
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.RELEASE,
            ),
        )


class scene_check(CommandBase):
    """Verify scene release name and integrity"""

    names = ('scene-check', 'scc')

    argument_definitions = {
        'RELEASE': {
            'type': utils.argtypes.release,
            'help': 'Release name or path to release content',
        },
    }

    @utils.cached_property
    def jobs(self):
        return (
            jobs.scene.SceneCheckJob(
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.RELEASE,
            ),
        )
