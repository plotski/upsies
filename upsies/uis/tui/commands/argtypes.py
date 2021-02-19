"""
CLI argument types

All types return normalized values and raise ValueError for invalid values.

A custom error message can be provided by raising
:class:`argparse.ArgumentTypeError`.
"""

import argparse
import os

from .... import constants, errors, trackers, utils


def client(value):
    """Name of a BitTorrent client from :mod:`~.utils.btclients`"""
    if value in utils.btclients.client_names():
        return value.lower()
    else:
        raise ValueError(f'Unsupported client: {value}')


def content(value):
    """Existing path to release file(s)"""
    path = release(value)
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f'No such file or directory: {value}')
    else:
        return path


def imghost(value):
    """Name of a image hosting service from :mod:`~.utils.imghosts`"""
    if value in utils.imghosts.imghost_names():
        return value.lower()
    else:
        raise ValueError(f'Unsupported image hosting service: {value}')


def integer(value):
    """Natural number (:class:`float` is rounded)"""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        raise ValueError(f'Not an integer: {value!r}')


def option(value):
    """Name of a configuration option"""
    if value in constants.OPTION_PATHS:
        return value.lower()
    else:
        raise ValueError(f'Unknown option: {value}')


def release(value):
    """Same as :func:`content`, but doesn't have to exist"""
    path = str(value)
    try:
        utils.scene.assert_not_abbreviated_filename(path)
    except errors.SceneError as e:
        raise argparse.ArgumentTypeError(e)
    else:
        return path


def scenedb(value):
    """Name of a scene release database from :mod:`~.utils.scene`"""
    if value in utils.scene.scenedb_names():
        return value.lower()
    else:
        raise ValueError(f'Unsupported scene release database: {value}')


def timestamp(value):
    """See :func:`.timestamp.parse`"""
    try:
        return utils.timestamp.parse(value)
    except TypeError as e:
        raise ValueError(e)


def tracker(value):
    """Name of a tracker from :mod:`~.trackers`"""
    if value in trackers.tracker_names():
        return value.lower()
    else:
        raise ValueError(f'Unsupported tracker: {value}')


def webdb(value):
    """Name of a movie/series database from :mod:`~.webdbs`"""
    if value in utils.webdbs.webdb_names():
        return value.lower()
    else:
        raise ValueError(f'Unsupported database: {value}')
