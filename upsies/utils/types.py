"""
CLI argument types

All types return normalized values and raise ValueError for invalid values.
"""

from .. import constants, utils


def integer(value):
    try:
        return int(float(value))
    except (ValueError, TypeError):
        raise ValueError(f'Not an integer: {value!r}')

def timestamp(value):
    try:
        return utils.timestamp.parse(value)
    except TypeError as e:
        raise ValueError(e)

def client(value):
    if value in constants.BTCLIENT_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported client: {value}')

def imghost(value):
    if value in constants.IMGHOST_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported image hosting service: {value}')

def scenedb(value):
    if value in constants.SCENEDB_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported scene release database: {value}')

def tracker(value):
    if value in constants.TRACKER_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported tracker: {value}')

def webdb(value):
    if value in constants.WEBDB_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported database: {value}')

def option(value):
    if value in constants.OPTION_PATHS:
        return value.lower()
    else:
        raise ValueError(f'Unknown option: {value}')
