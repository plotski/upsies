"""
API for image hosting services
"""

from .. import CaseInsensitiveString, subclasses, submodules
from .base import ImageHostBase
from .common import UploadedImage


def imghosts():
    """Return list of :class:`.ImageHostBase` subclasses"""
    return subclasses(ImageHostBase, submodules(__package__))


def imghost(name, config=None):
    """
    Create :class:`.ImageHostBase` instance

    :param str name: Name of the image hosting service. A subclass of
        :class:`.ImageHostBase` with the same :attr:`~.ImageHostBase.name` must
        exist in one of this package's submodules.
    :param dict config: User configuration passed to the subclass specified by
        `name`

    :raise ValueError: if no matching subclass can be found

    :return: :class:`.ImageHostBase` instance
    """
    for imghost in imghosts():
        if imghost.name == name:
            return imghost(config=config)
    raise ValueError(f'Unsupported image hosting service: {name}')


def imghost_names():
    """Return sequence of valid `name` arguments for :func:`.imghost`"""
    return sorted(CaseInsensitiveString(cls.name) for cls in imghosts())
