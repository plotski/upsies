"""
Communication with BitTorrent clients
"""

from ._base import ClientApiBase  # isort:skip
from . import transmission


def client(name, **kwargs):
    """
    Create client instance

    :param str name: Name of a public module in this package
    :param kwargs: All keyword arguments are passed to the module's
        :class:`ClientApi` class

    :raise ValueError: if `name` does not correspond to an existing module in
        this package

    :return: :class:`ClientApi` instance
    """
    try:
        module = globals()[name]
    except KeyError:
        raise ValueError(f'Unsupported client: {name}')
    else:
        return module.ClientApi(**kwargs)
