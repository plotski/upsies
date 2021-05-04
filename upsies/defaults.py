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
"""Defaults for configuration options"""


def option_paths():
    """Tuple of configuration option paths (`<section>.<subsection>.<option>`)"""

    def _get_option_paths(cfg, parents=()):
        paths = []
        for k, v in cfg.items():
            k_parents = parents + (k,)
            if isinstance(v, dict):
                paths.extend(_get_option_paths(v, parents=k_parents))
            else:
                paths.append('.'.join(k_parents))
        return tuple(sorted(paths))

    return _get_option_paths(defaults)


def option_type(option_path):
    filename, section, option = option_path.split('.', maxsplit=2)
    return type(defaults[filename][section][option])
