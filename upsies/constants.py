"""
Fixed values that do not change during runtime
"""

import os

from xdg.BaseDirectory import xdg_cache_home as XDG_CACHE_HOME
from xdg.BaseDirectory import xdg_config_home as XDG_CONFIG_HOME

CACHE_DIRPATH = os.path.join(XDG_CACHE_HOME, 'upsies')
"""Path cache directory"""

CONFIG_FILEPATH = os.path.join(XDG_CONFIG_HOME, 'upsies', 'config.ini')
"""Path to general configuration file"""

TRACKERS_FILEPATH = os.path.join(XDG_CONFIG_HOME, 'upsies', 'trackers.ini')
"""Path to trackers configuration file"""

IMGHOSTS_FILEPATH = os.path.join(XDG_CONFIG_HOME, 'upsies', 'imghosts.ini')
"""Path to image hosting services configuration file"""

CLIENTS_FILEPATH = os.path.join(XDG_CONFIG_HOME, 'upsies', 'clients.ini')
"""Path to BitTorrent clients configuration file"""

def _get_option_paths(cfg, parents=()):
    paths = []
    for k, v in cfg.items():
        k_parents = parents + (k,)
        if isinstance(v, dict):
            paths.extend(_get_option_paths(v, parents=k_parents))
        else:
            paths.append('.'.join(k_parents))
    return tuple(sorted(paths))

VIDEO_FILE_EXTENSIONS = ('mkv', 'mp4', 'ts', 'avi', 'vob')
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
