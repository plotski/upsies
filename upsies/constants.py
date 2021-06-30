"""
Fixed values that do not change during runtime
"""

import os

from xdg.BaseDirectory import xdg_cache_home as XDG_CACHE_HOME
from xdg.BaseDirectory import xdg_config_home as XDG_CONFIG_HOME

from . import __project_name__

CACHE_DIRPATH = os.path.join(XDG_CACHE_HOME, __project_name__)
"""Path cache directory"""

CONFIG_FILEPATH = os.path.join(XDG_CONFIG_HOME, __project_name__, 'config.ini')
"""Path to general configuration file"""

TRACKERS_FILEPATH = os.path.join(XDG_CONFIG_HOME, __project_name__, 'trackers.ini')
"""Path to trackers configuration file"""

IMGHOSTS_FILEPATH = os.path.join(XDG_CONFIG_HOME, __project_name__, 'imghosts.ini')
"""Path to image hosting services configuration file"""

CLIENTS_FILEPATH = os.path.join(XDG_CONFIG_HOME, __project_name__, 'clients.ini')
"""Path to BitTorrent clients configuration file"""

VIDEO_FILE_EXTENSIONS = ('mkv', 'mp4', 'avi', 'wmv', 'vob', 'm2ts', 'mts', 'ts')
"""Sequence of file extensions to recognize video files"""

GUESSIT_OPTIONS = {
    'expected_title': [
        'The Collector',
        'xXx',
    ],
    'advanced_config': {
        # https://github.com/guessit-io/guessit/pull/678
        'audio_codec': {
            'audio_channels': {
                '1.0': [
                    '1ch',
                    'mono',
                    're:(1[\\W_]0(?:ch)?)(?=[^\\d]|$)',
                ],
            },
        },
    },
}
"""`options` argument for :meth:`.GuessItApi.guessit`"""
