"""
CLI argument types

All types return normalized values and raise ValueError for invalid values.
"""

from .. import constants, trackers, utils

BTCLIENT_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in utils.btclients.clients()]
IMGHOST_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in utils.imghosts.imghosts()]
TRACKER_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in trackers.trackers()]
WEBDB_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in utils.webdbs.webdbs()]


def integer(string):
    return int(string)

def timestamp(string):
    return utils.timestamp.parse(string)

def webdb(string):
    if string in WEBDB_NAMES:
        return string.lower()
    else:
        raise ValueError(f'Unsupported online databasae: {string}')

def tracker(string):
    if string in TRACKER_NAMES:
        return string.lower()
    else:
        raise ValueError(f'Unsupported tracker: {string}')

def client(string):
    if string in BTCLIENT_NAMES:
        return string.lower()
    else:
        raise ValueError(f'Unsupported client: {string}')

def imghost(string):
    if string in IMGHOST_NAMES:
        return string.lower()
    else:
        raise ValueError(f'Unsupported image hosting service: {string}')

def option(string):
    if string in constants.OPTION_PATHS:
        return string.lower()
    else:
        raise ValueError(f'Unknown option: {string}')
