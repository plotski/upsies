import base64
import os

from xdg.BaseDirectory import xdg_config_home as XDG_CONFIG_HOME

trackers_filepath = os.path.join(XDG_CONFIG_HOME, 'upsies', 'trackers.ini')
clients_filepath = os.path.join(XDG_CONFIG_HOME, 'upsies', 'clients.ini')


class _TrackerConfig(dict):
    _defaults = {
        'username' : '',
        'password' : '',
        'announce' : '',
        'source'   : '',
        'exclude'  : [],
    }

    def __new__(cls, **kwargs):
        return {**cls._defaults, **kwargs}


config = {
    'trackers': {
        'dummy': _TrackerConfig(
            base_url='http://localhost',
            source='DMY',
            announce='http://localhost:12345/dummy/announce',
            image_host='dummy',
        ),
        'nbl': _TrackerConfig(
            base_url=base64.b64decode('aHR0cHM6Ly9uZWJ1bGFuY2UuaW8=').decode('ascii'),
            source='NBL',
        ),
    },

    'imghosts': {
        'dummy': {},
        'imgbox': {},
    },

    'clients': {
        'dummy': {},
        'transmission': {
            'url': 'http://localhost:9091/transmission/rpc',
            'username': '',
            'password': '',
        },
    },
}


def _get_paths(cfg, parents=()):
    paths = []
    for k, v in cfg.items():
        k_parents = parents + (k,)
        if isinstance(v, dict):
            paths.extend(_get_paths(v, parents=k_parents))
        else:
            paths.append('.'.join(k_parents))
    return tuple(sorted(paths))

OPTION_PATHS = _get_paths(config)
