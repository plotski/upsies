"""
CLI argument types

Argument type names should match the ``metavar`` argument given to
:meth:`argparse.ArgumentParser.add_argument` and raise ValueError.
"""

from ... import constants, trackers, utils

WEBDB_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in utils.webdbs.webdbs()]
TRACKER_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in trackers.trackers()]
IMGHOST_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in utils.imghosts.imghosts()]
BTCLIENT_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in utils.btclients.clients()]


def NUMBER(string):
    return int(string)

def TIMESTAMP(string):
    return utils.timestamp.parse(string)

def WEBDB(string):
    if string in WEBDB_NAMES:
        return string.lower()
    else:
        raise ValueError(f'Unsupported online databasae: {string}')

def TRACKER(string):
    if string in TRACKER_NAMES:
        return string.lower()
    else:
        raise ValueError(f'Unsupported tracker: {string}')

def CLIENT(string):
    if string in BTCLIENT_NAMES:
        return string.lower()
    else:
        raise ValueError(f'Unsupported client: {string}')

def IMAGEHOST(string):
    if string in IMGHOST_NAMES:
        return string.lower()
    else:
        raise ValueError(f'Unsupported image hosting service: {string}')

def OPTION(string):
    if string in constants.OPTION_PATHS:
        return string.lower()
    else:
        raise ValueError(f'Unknown option: {string}')
