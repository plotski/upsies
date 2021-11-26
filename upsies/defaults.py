import functools

from . import constants, trackers, utils

defaults = {
    'config': {
        'main': {
            'cache_directory': utils.configfiles.config_value(
                value=constants.DEFAULT_CACHE_DIRECTORY,
                description='Where to store generated files.',
            ),
            'max_cache_size': utils.configfiles.config_value(
                value=utils.types.Bytes.from_string('20 MB'),
                description=(
                    'Maximum size of cache directory. '
                    'Units like "kB" and "MiB" are interpreted.'
                ),
            ),
        },
    },

    'trackers': {
        tracker.name: tracker.TrackerConfig()
        for tracker in trackers.trackers()
    },

    'imghosts': {
        imghost.name: imghost.default_config
        for imghost in utils.imghosts.imghosts()
    },

    'clients': {
        client.name: client.default_config
        for client in utils.btclients.clients()
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
