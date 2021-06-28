"""
Scene release search and verification
"""

from ... import utils
from .. import release
from . import predb, srrdb
from .base import SceneDbApiBase
from .find import SceneQuery, search
from .verify import (assert_not_abbreviated_filename, is_scene_release,
                     release_files, verify_release, verify_release_files,
                     verify_release_name)


def scenedbs():
    """Return list of :class:`.SceneDbApiBase` subclasses"""
    return utils.subclasses(SceneDbApiBase, utils.submodules(__package__))


def scenedb(name, config=None):
    """
    Create :class:`.SceneDbApiBase` instance

    :param str name: Name of the scene release database. A subclass of
        :class:`.SceneDbApiBase` with the same :attr:`~.SceneDbApiBase.name` must
        exist in one of this package's submodules.
    :param dict config: User configuration passed to the subclass specified by
        `name`

    :raise ValueError: if no matching subclass can be found

    :return: :class:`.SceneDbApiBase` instance
    """
    for scenedb in scenedbs():
        if scenedb.name == name:
            return scenedb(config=config)
    raise ValueError(f'Unsupported scene release database: {name}')


def scenedb_names():
    """Return sequence of valid `name` arguments for :func:`.scenedb`"""
    return sorted(utils.CaseInsensitiveString(cls.name) for cls in scenedbs())
