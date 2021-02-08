"""
CLI argument types

All types return normalized values and raise ValueError for invalid values.

A custom error message can be provided by raising
:class:`argparse.ArgumentTypeError`.
"""

import argparse

from .... import errors, utils


def content(value):
    """Existing path to release file(s)"""
    path = str(value)
    try:
        utils.scene.assert_not_abbreviated_filename(path)
    except errors.SceneError as e:
        raise argparse.ArgumentTypeError(e)
    else:
        return path

def release(value):
    """Same as :func:`content`, but doesn't have to exist"""
    return content(value)
