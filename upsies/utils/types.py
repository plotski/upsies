"""
CLI argument types

All types return normalized values and raise ValueError for invalid values.
"""

from .. import constants, trackers, utils

BTCLIENT_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in utils.btclients.clients()]
IMGHOST_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in utils.imghosts.imghosts()]
TRACKER_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in trackers.trackers()]
WEBDB_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in utils.webdbs.webdbs()]


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
    if value in BTCLIENT_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported client: {value}')

def imghost(value):
    if value in IMGHOST_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported image hosting service: {value}')

def tracker(value):
    if value in TRACKER_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported tracker: {value}')

def webdb(value):
    if value in WEBDB_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported database: {value}')

def option(value):
    if value in constants.OPTION_PATHS:
        return value.lower()
    else:
        raise ValueError(f'Unknown option: {value}')
