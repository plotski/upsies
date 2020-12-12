"""
API for BitTorrent clients
"""

from ... import utils
from .base import ClientApiBase


def clients():
    """Return list of :class:`.ClientApiBase` subclasses"""
    return utils.subclasses(ClientApiBase, utils.submodules(__package__))


def client(name, **kwargs):
    """
    Create :class:`.ClientApiBase` instance

    :param str name: Name of the client. A subclass of :class:`.ClientApiBase`
        with the same :attr:`~.ClientApiBase.name` must exist in one of this
        package's submodules
    :param kwargs: All keyword arguments are passed to the subclass specified by
        `name`

    :raise ValueError: if no matching subclass can be found

    :return: :class:`.ClientApiBase` instance
    """
    for client in clients():
        if client.name == name:
            return client(**kwargs)
    raise ValueError(f'Unsupported client: {name}')
