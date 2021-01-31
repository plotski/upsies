"""
Scene release search and validation
"""

import asyncio
import os
import re

from ... import errors
from .. import subclasses, submodules
from . import predb, srrdb
from .base import SceneDbApiBase


def scenedbs():
    """Return list of :class:`.SceneDbApiBase` subclasses"""
    return subclasses(SceneDbApiBase, submodules(__package__))


def scenedb(name, **kwargs):
    """
    Create :class:`.SceneDbApiBase` instance

    :param str name: Name of the scene release database. A subclass of
        :class:`.SceneDbApiBase` with the same :attr:`~.SceneDbApiBase.name` must
        exist in one of this package's submodules.
    :param kwargs: All keyword arguments are passed to the subclass specified by
        `name`

    :raise ValueError: if no matching subclass can be found

    :return: :class:`.ClientApiBase` instance
    """
    for scenedb in scenedbs():
        if scenedb.name == name:
            return scenedb(**kwargs)
    raise ValueError(f'Unsupported scene release database: {name}')


async def search(*args, **kwargs):
    """
    Concurrently search with all :class:`~.SceneDbApiBase` subclasses

    All arguments are passed on to each :meth:`~.SceneDbApiBase.search` method.

    :return: Deduplicated :class:`list` of release names as :class:`str`
    """
    # TODO: Allow custom arguments for SceneDbApiBase subclasses (e.g. for user
    #       authentication): Add "class_args" argument: dict that maps
    #       SceneDb.name values to (('posarg', ...), {'kw': 'arg', ...}) tuples
    #       which are passed to the corresponding subclass.
    searches = [asyncio.ensure_future(SceneDb().search(*args, **kwargs))
                for SceneDb in scenedbs()]
    done, pending = await asyncio.wait(searches, return_when=asyncio.ALL_COMPLETED)
    assert not pending, pending

    combined_results = set()
    exceptions = []
    for task in done:
        try:
            results = task.result()
        except errors.SceneError as e:
            exceptions.append(e)
        else:
            combined_results.update(results)

    return sorted(combined_results, key=str.casefold) + exceptions


_abbreviated_scene_filename_regex = re.compile(r'^[a-z0-9]+[-\.][a-z0-9]+[^A-Z]*\.[a-z]{3}$')

def is_abbreviated_filename(filepath):
    """
    Whether `filepath` is an abbreviated scene release name like
    ``abd-mother.mkv``
    """
    filename = os.path.basename(filepath)
    return bool(_abbreviated_scene_filename_regex.search(filename))
