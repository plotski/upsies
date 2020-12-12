import os

from xdg.BaseDirectory import xdg_config_home as XDG_CONFIG_HOME

from . import defaults

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
