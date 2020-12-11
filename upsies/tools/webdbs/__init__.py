"""
API for querying services like IMDb
"""

from ... import utils
from . import imdb, tmdb, tvmaze
from .base import WebDbApiBase
from .common import Query, SearchResult, Type


def webdbs():
    """Return list of :class:`.WebDbApiBase` subclasses"""
    return utils.subclasses(WebDbApiBase, utils.submodules(__package__))


def webdb(name, **kwargs):
    """
    Create :class:`.WebDbApiBase` instance

    :param str name: Name of the DB. A subclass of :class:`.WebDbApiBase` with
        the same :attr:`~.WebDbApiBase.name` must exist in one of this package's
        submodules
    :param kwargs: All keyword arguments are passed to the subclass specified by
        `name`

    :raise ValueError: if no matching subclass can be found

    :return: :class:`.WebDbApiBase` instance
    """
    for cls in webdbs():
        if cls.name == name:
            return cls(**kwargs)
    raise ValueError(f'Unsupported web DB: {name}')
