"""
Searching for and verifying scene release
"""

from .... import jobs, utils
from . import argtypes
from .base import CommandBase


class scene_search(CommandBase):
    """Search for scene release name"""

    names = ('scene-search', 'scs')

    argument_definitions = {
        'RELEASE': {
            'type': argtypes.release,
            'help': 'Release name or path to release content',
        },
    }

    @utils.cached_property
    def jobs(self):
        return (
            jobs.scene.SceneSearchJob(
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.RELEASE,
            ),
        )
