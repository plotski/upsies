"""
Various cleanup tasks before the application terminates
"""

from .utils import http

import logging  # isort:skip
_log = logging.getLogger(__name__)


def cleanup(config):
    """This function should be called by the UI before the applicatin terminates"""
    _log.debug('Cleaning up')
    http.close()
    _log.debug('Done cleaning up')
