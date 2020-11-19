"""
Common API for image hosting services
"""

# isort:skip_file
from ._base import UploaderBase
from ._common import UploadedImage
from . import dummy, imgbox


def uploader(name, **kwargs):
    """
    Create Uploader instance

    :param str name: Name of a public module in this package
    :param kwargs: All keyword arguments are passed to the module's
        :class:`Uploader` class

    :raise ValueError: if `name` does not correspond to an existing module in
        this package

    :return: :class:`Uploader` instance
    """
    try:
        module = globals()[name]
    except KeyError:
        raise ValueError(f'Unsupported image host: {name}')
    else:
        return module.Uploader(**kwargs)
