"""
Fixed values that do not change during runtime
"""

import os

from xdg.BaseDirectory import xdg_config_home as XDG_CONFIG_HOME

from . import defaults, trackers
from .utils import CaseInsensitiveString, btclients, imghosts, scene, webdbs

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

OPTION_PATHS = _get_option_paths(defaults.defaults)
"""Tuple of configuration option paths (`<section>.<subsection>.<option>`)"""

VIDEO_FILE_EXTENSIONS = ('mkv', 'mp4', 'ts', 'avi')
"""Sequence of file extensions to recognize video files"""

BTCLIENT_NAMES = [CaseInsensitiveString(cls.name) for cls in btclients.clients()]
"""Valid `name` arguments for :func:`.btclients.client`"""

IMGHOST_NAMES = [CaseInsensitiveString(cls.name) for cls in imghosts.imghosts()]
"""Valid `name` arguments for :func:`.imghosts.imghost`"""

SCENEDB_NAMES = [CaseInsensitiveString(cls.name) for cls in scene.scenedbs()]
"""Valid `name` arguments for :func:`.scene.scenedb`"""

TRACKER_NAMES = [CaseInsensitiveString(cls.name) for cls in trackers.trackers()]
"""Valid `name` arguments for :func:`.trackers.tracker`"""

WEBDB_NAMES = [CaseInsensitiveString(cls.name) for cls in webdbs.webdbs()]
"""Valid `name` arguments for :func:`.webdbs.webdbs`"""

GUESSIT_OPTIONS = {
    'expected_title': [
        'The Collector',
    ],
    "advanced_config": {
    },
}
"""`options` argument for :meth:`.GuessItApi.guessit`"""
