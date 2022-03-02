__project_name__ = 'upsies'
__description__ = 'Media metadata aggregator'
__homepage__ = 'https://upsies.readthedocs.io'
__version__ = '2022.03.02alpha2'
__author__ = 'plotski'
__author_email__ = 'plotski@example.org'


def application_setup(config):
    """
    This function should be called by the UI ASAP when `config` is available

    :param config: :class:`~.configfiles.ConfigFiles` instance
    """
    import os

    from . import utils

    utils.http.cache_directory = os.path.join(
        config['config']['main']['cache_directory'],
        'http_responses',
    )


def application_shutdown(config):
    """
    This function should be called by the UI before the applicatin terminates

    :param config: :class:`~.configfiles.ConfigFiles` instance
    """
    import asyncio

    from . import utils

    # Maintain maximum cache size
    utils.fs.limit_directory_size(
        path=config['config']['main']['cache_directory'],
        max_total_size=config['config']['main']['max_cache_size'],
    )

    # Remove empty files and directories
    utils.fs.prune_empty(
        path=config['config']['main']['cache_directory'],
        files=True,
        directories=True,
    )

    utils.get_aioloop().run_until_complete(utils.http.close())
