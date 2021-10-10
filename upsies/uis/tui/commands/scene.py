"""
Searching for and verifying scene release
"""

from .... import jobs, utils
from .base import CommandBase


class scene_search(CommandBase):
    """
    Find scene releases that match RELEASE

    The search query is not a simple text search. Instead, RELEASE is
    interpreted according to the usual release name format.

    Examples:

    Foo.1995.1080p.x264
       Find any x264 encodes of "Foo" from 1995 in 1080p.

    Foo.1995.BluRay.x264-ASDF
       Find any Blu-ray x264 encodes of "Foo" from 1995 from group "ASDF".

    Foo.S03.720p
       Find any 720p release of the third season of "Foo".

    Foo.S01E01E02 S02E03E04.720p
       Find any 720p encodes of episodes 1 & 2 from season 1 and episodes 3 & 4
       from season 2.
    """

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
    """
    Verify scene release name and integrity

    If RELEASE is a scene release, make sure it has the correct file size(s) and
    is named properly.
    """

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
