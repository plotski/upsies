"""
API for BitTorrent clients
"""

from .. import CaseInsensitiveString, subclasses, submodules
from .base import ClientApiBase


def clients():
    """Return list of :class:`.ClientApiBase` subclasses"""
    return subclasses(ClientApiBase, submodules(__package__))


def client(name, config=None):
    """
    Create :class:`.ClientApiBase` instance

    :param str name: Name of the client. A subclass of :class:`.ClientApiBase`
        with the same :attr:`~.ClientApiBase.name` must exist in one of this
        package's submodules.
    :param dict config: User configuration passed to the subclass specified by
        `name`

    :raise ValueError: if no matching subclass can be found

    :return: :class:`.ClientApiBase` instance
    """
    for client in clients():
        if client.name == name:
            return client(config=config)
    raise ValueError(f'Unsupported client: {name}')


def client_names():
    """Return sequence of valid `name` arguments for :func:`.client`"""
    return sorted(CaseInsensitiveString(cls.name) for cls in clients())
