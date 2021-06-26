import functools

from . import constants, trackers, utils

defaults = {
    'config': {
        'main': {
            'cache_directory': constants.CACHE_DIRPATH,
            'max_cache_size': utils.types.Bytes.from_string('20 MB'),
        },
    },

    'trackers': {
        tracker.name: tracker.TrackerConfig()
        for tracker in trackers.trackers()
    },

    'imghosts': {
        'dummy': {
            'hostname': 'localhost',
        },
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
"""Defaults for configuration options"""


@functools.lru_cache(maxsize=None)
def option_paths():
    """Tuple of configuration option paths (`<section>.<subsection>.<option>`)"""
    return utils.configfiles.ConfigFiles(defaults).paths


def option_type(option_path):
    filename, section, option = option_path.split('.', maxsplit=2)
    return type(defaults[filename][section][option])
