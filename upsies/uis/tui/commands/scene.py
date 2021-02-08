"""
Search for scene release
"""

from .... import constants, jobs, utils
from . import argtypes
from .base import CommandBase


class scene_search(CommandBase):
    """Search for scene release"""

    names = ('scene-search', 'scs')

    argument_definitions = {
        'SCENEDB': {
            'type': utils.types.scenedb,
            'nargs': '?',
            'default': jobs.scene.SceneSearchJob.default_scenedb,
            'help': ('Case-insensitive scene release database name\n'
                     'Supported databases: ' + ', '.join(constants.SCENEDB_NAMES) + '\n'
                     f'Default: {jobs.scene.SceneSearchJob.default_scenedb}'),
        },
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
                scenedb=utils.scene.scenedb(self.args.SCENEDB),
                content_path=self.args.RELEASE,
            ),
        )
