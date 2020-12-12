"""
API for trackers

:class:`~.base.TrackerBase` provide a common interface for all trackers. They
have two main purposes:

1. Specify jobs that generate metadata, e.g. torrent creation, running
   ``mediainfo`` and searching for IDs.

2. Provide coroutine methods, e.g. for :meth:`~.base.TrackerBase.upload`\ ing
   the generated metadata.
"""

from .. import utils
from . import dummy, nbl
from .base import TrackerBase


def trackers():
    """Return list of :class:`.TrackerBase` subclasses"""
    return utils.subclasses(TrackerBase, utils.submodules(__package__))


def tracker(name, **kwargs):
    """
    Create :class:`.TrackerBase` instance

    :param str name: Name of the tracker. A subclass of :class:`.TrackerBase`
        with the same :attr:`~.TrackerBase.name` must exist in one of this
        package's submodules.
    :param kwargs: All keyword arguments are passed to the subclass specified by
        `name`

    :raise ValueError: if no matching subclass can be found

    :return: :class:`.TrackerBase` instance
    """
    for cls in trackers():
        if cls.name == name:
            return cls(**kwargs)
    raise ValueError(f'Unsupported tracker: {name}')
