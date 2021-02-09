"""
CLI argument types

All types return normalized values and raise ValueError for invalid values.
"""

import enum

from .. import constants, utils


def integer(value):
    """Natural number (:class:`float` is rounded)"""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        raise ValueError(f'Not an integer: {value!r}')

def timestamp(value):
    """See :func:`.timestamp.parse`"""
    try:
        return utils.timestamp.parse(value)
    except TypeError as e:
        raise ValueError(e)

def client(value):
    """Name of a BitTorrent client from :mod:`~.utils.btclients`"""
    if value in constants.BTCLIENT_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported client: {value}')

def imghost(value):
    """Name of a image hosting service from :mod:`~.utils.imghosts`"""
    if value in constants.IMGHOST_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported image hosting service: {value}')

def scenedb(value):
    """Name of a scene release database from :mod:`~.utils.scene`"""
    if value in constants.SCENEDB_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported scene release database: {value}')

def tracker(value):
    """Name of a tracker from :mod:`~.trackers`"""
    if value in constants.TRACKER_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported tracker: {value}')

def webdb(value):
    """Name of a movie/series database from :mod:`~.webdbs`"""
    if value in constants.WEBDB_NAMES:
        return value.lower()
    else:
        raise ValueError(f'Unsupported database: {value}')

def option(value):
    """Name of a configuration option"""
    if value in constants.OPTION_PATHS:
        return value.lower()
    else:
        raise ValueError(f'Unknown option: {value}')


class ReleaseType(enum.Enum):
    """
    Enum with the values ``movie``, ``season``, ``episode`` and
    ``unknown``

    ``series`` is an alias for ``season``.

    All values are truthy except for ``unknown``.
    """

    movie = 'movie'
    season = 'season'
    series = 'season'
    episode = 'episode'
    unknown = 'unknown'

    def __bool__(self):
        return self is not self.unknown

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f'{type(self).__name__}.{self.value}'


class SceneCheckResult(enum.Enum):
    """
    Enum with the values ``true``, ``false``, ``renamed``, ``altered`` and
    ``unknown``

    All values are falsy except for ``true``.
    """

    true = 'true'
    false = 'false'
    renamed = 'renamed'
    altered = 'altered'
    unknown = 'unknown'

    def __bool__(self):
        return self is self.true

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f'{type(self).__name__}.{self.value}'
