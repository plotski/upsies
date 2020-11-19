"""
Common API for image hosting services
"""

# isort:skip_file
from ._base import ImageHostBase
from ._common import UploadedImage
from . import dummy, imgbox


def imghost(name, **kwargs):
    """
    Create ImageHost instance

    :param str name: Name of a public module in this package
    :param kwargs: All keyword arguments are passed to the module's
        :class:`ImageHost` class

    :raise ValueError: if `name` does not correspond to an existing module in
        this package

    :return: :class:`ImageHost` instance
    """
    try:
        module = globals()[name]
    except KeyError:
        raise ValueError(f'Unsupported image host: {name}')
    else:
        return module.ImageHost(**kwargs)
