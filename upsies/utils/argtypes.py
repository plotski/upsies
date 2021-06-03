"""
CLI argument types

All types return normalized values and raise ValueError for invalid values.

A custom error message can be provided by raising
:class:`argparse.ArgumentTypeError`.
"""

import argparse
import os


def client(value):
    """Name of a BitTorrent client from :mod:`~.utils.btclients`"""
    from . import btclients
    if value in btclients.client_names():
        return value.lower()
    else:
        raise argparse.ArgumentTypeError(f'Unsupported client: {value}')


def content(value):
    """Existing path to release file(s)"""
    path = release(value)
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f'No such file or directory: {value}')
    else:
        return path


def imghost(value):
    """Name of a image hosting service from :mod:`~.utils.imghosts`"""
    from . import imghosts
    if value in imghosts.imghost_names():
        return value.lower()
    else:
        raise argparse.ArgumentTypeError(f'Unsupported image hosting service: {value}')


def integer(value):
    """Natural number (:class:`float` is rounded)"""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError(f'Not an integer: {value!r}')


def option(value):
    """Name of a configuration option"""
    from .. import defaults
    if value in defaults.option_paths():
        return value.lower()
    else:
        raise argparse.ArgumentTypeError(f'Unknown option: {value}')


def release(value):
    """Same as :func:`content`, but doesn't have to exist"""
    from .. import errors
    from . import scene
    path = str(value)
    try:
        scene.assert_not_abbreviated_filename(path)
    except errors.SceneError as e:
        raise argparse.ArgumentTypeError(e)
    else:
        return path


def scenedb(value):
    """Name of a scene release database from :mod:`~.utils.scene`"""
    from . import scene
    if value in scene.scenedb_names():
        return value.lower()
    else:
        raise argparse.ArgumentTypeError(f'Unsupported scene release database: {value}')


def timestamp(value):
    """See :func:`.timestamp.parse`"""
    from . import timestamp
    try:
        return timestamp.parse(value)
    except (ValueError, TypeError) as e:
        raise argparse.ArgumentTypeError(e)


def tracker(value):
    """Name of a tracker from :mod:`~.trackers`"""
    from .. import trackers
    if value in trackers.tracker_names():
        return value.lower()
    else:
        raise argparse.ArgumentTypeError(f'Unsupported tracker: {value}')


def webdb(value):
    """Name of a movie/series database from :mod:`~.webdbs`"""
    from . import webdbs
    if value in webdbs.webdb_names():
        return value.lower()
    else:
        raise argparse.ArgumentTypeError(f'Unsupported database: {value}')
