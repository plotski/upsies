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
        'nbl': _TrackerConfig(
            source='NBL',
        ),
        'bb': _TrackerConfig(
            source='bB',
            exclude=[
                r'\.(?i:jpg)$',
                r'\.(?i:png)$',
                r'\.(?i:nfo)$',
                r'\.(?i:txt)$',
                rf'(?:{os.path.sep}|^)(?i:sample)(?:{os.path.sep}|\.[a-zA-Z0-9]+$)',
                rf'(?:{os.path.sep}|^)(?i:proof)(?:{os.path.sep}|\.[a-zA-Z0-9]+$)',
            ],
        ),
    },

    'clients': {
        'transmission': {
            'url': 'http://localhost:9091/transmission/rpc',
            'username': '',
            'password': '',
        },
    }
}
