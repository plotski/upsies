"""Constants docstring"""

import os

from xdg.BaseDirectory import xdg_config_home as XDG_CONFIG_HOME

TRACKERS_FILEPATH = os.path.join(XDG_CONFIG_HOME, 'upsies', 'trackers.ini')
"""Path to trackers configuration file"""

CLIENTS_FILEPATH = os.path.join(XDG_CONFIG_HOME, 'upsies', 'clients.ini')
"""Path to BitTorrent clients configuration file"""

# TODO: If _config.Config was a singleton, we could get the option paths from
#       Config().path.
from . import _defaults


def _get_option_paths(cfg, parents=()):
    paths = []
    for k, v in cfg.items():
        k_parents = parents + (k,)
        if isinstance(v, dict):
            paths.extend(_get_option_paths(v, parents=k_parents))
        else:
            paths.append('.'.join(k_parents))
    return tuple(sorted(paths))

OPTION_PATHS = _get_option_paths(_defaults.defaults)
"""Tuple of configuration option paths (`<section>.<subsection>.<option>`)"""
