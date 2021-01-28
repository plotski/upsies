"""
Scene release search and validation
"""

import asyncio

from ... import errors
from .. import subclasses, submodules
from . import predb, srrdb
from .base import SceneDbBase


def scenedbs():
    """Return list of :class:`.SceneDbBase` subclasses"""
    return subclasses(SceneDbBase, submodules(__package__))


def scenedb(name, **kwargs):
    """
    Create :class:`.SceneDbBase` instance

    :param str name: Name of the scene release database. A subclass of
        :class:`.SceneDbBase` with the same :attr:`~.SceneDbBase.name` must
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
    Concurrently search with all :class:`~.SceneDbBase` subclasses

    All arguments are passed on to each :meth:`~.SceneDbBase.search` method.

    :return: Deduplicated :class:`list` of release names as :class:`str`
    """
    # TODO: Allow custom arguments for SceneDbBase subclasses (e.g. for user
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
