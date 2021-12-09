__project_name__ = 'upsies'
__description__ = 'Media metadata aggregator'
__homepage__ = 'https://upsies.readthedocs.io'
__version__ = '2021.12.09'
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

    utils.fs.limit_directory_size(
        path=config['config']['main']['cache_directory'],
        max_total_size=config['config']['main']['max_cache_size'],
    )

    utils.get_aioloop().run_until_complete(utils.http.close())
