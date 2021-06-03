__project_name__ = 'upsies'
__description__ = 'Media metadata aggregator'
__homepage__ = 'https://upsies.readthedocs.io'
__version__ = '2021.06.03a0'
__author__ = 'plotski'
__author_email__ = 'plotski@example.org'


def application_setup(config):
    """
    This function should be called by the UI ASAP when `config` is available

    :param config: :class:`~.configfiles.ConfigFiles` instance
    """
    from .utils import http
    http.cache_directory = config['config']['main']['cache_directory']


def application_shutdown(config):
    """
    This function should be called by the UI before the applicatin terminates

    :param config: :class:`~.configfiles.ConfigFiles` instance
    """
    from .utils import fs, http
    http.close()
    fs.limit_directory_size(
        path=config['config']['main']['cache_directory'],
        max_total_size=config['config']['main']['max_cache_size'],
    )
