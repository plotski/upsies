__project_name__ = 'upsies'
__description__ = 'Media metadata aggregator'
__homepage__ = 'https://upsies.readthedocs.io'
__version__ = '2021.07.13'
__author__ = 'plotski'
__author_email__ = 'plotski@example.org'


def application_setup(config):
    """
    This function should be called by the UI ASAP when `config` is available

    :param config: :class:`~.configfiles.ConfigFiles` instance
    """
    from . import utils
    utils.http.cache_directory = config['config']['main']['cache_directory']


def application_shutdown(config):
    """
    This function should be called by the UI before the applicatin terminates

    :param config: :class:`~.configfiles.ConfigFiles` instance
    """
    from . import utils
    utils.http.close()
    utils.fs.limit_directory_size(
        path=config['config']['main']['cache_directory'],
        max_total_size=config['config']['main']['max_cache_size'],
    )
