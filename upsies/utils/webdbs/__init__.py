"""
API for querying services like IMDb
"""

from .. import CaseInsensitiveString, subclasses, submodules
from . import imdb, tmdb, tvmaze
from .base import WebDbApiBase
from .common import Person, Query, SearchResult


def webdbs():
    """Return list of :class:`.WebDbApiBase` subclasses"""
    return subclasses(WebDbApiBase, submodules(__package__))


def webdb(name, config=None):
    """
    Create :class:`.WebDbApiBase` instance

    :param str name: Name of the DB. A subclass of :class:`.WebDbApiBase` with
        the same :attr:`~.WebDbApiBase.name` must exist in one of this package's
        submodules.
    :param dict config: User configuration passed to the subclass specified by
        `name`

    :raise ValueError: if no matching subclass can be found

    :return: :class:`.WebDbApiBase` instance
    """
    for cls in webdbs():
        if cls.name == name:
            return cls(config=config)
    raise ValueError(f'Unsupported web database: {name}')


def webdb_names():
    """Return sequence of valid `name` arguments for :func:`.webdb`"""
    return sorted(CaseInsensitiveString(cls.name) for cls in webdbs())
