"""
Fixed values that do not change during runtime
"""

import os

from xdg.BaseDirectory import xdg_config_home as XDG_CONFIG_HOME

CONFIG_FILEPATH = os.path.join(XDG_CONFIG_HOME, 'upsies', 'config.ini')
"""Path to general configuration file"""

TRACKERS_FILEPATH = os.path.join(XDG_CONFIG_HOME, 'upsies', 'trackers.ini')
"""Path to trackers configuration file"""

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

VIDEO_FILE_EXTENSIONS = ('mkv', 'mp4', 'ts', 'avi')
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
