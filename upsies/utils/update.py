"""
Find most recent version
"""

import re

from .. import __project_name__, __version__
from . import http

import logging  # isort:skip
_log = logging.getLogger(__name__)


_INFO_URL_PATTERN = 'https://pypi.org/pypi/{project_name}/json'
_MAX_CACHE_AGE = 3600  # 1 hour


def _fix_version(version):
    match = re.search(r'^(\d{4})\.(\d+)\.(\d+)(.*)$', version)
    if match:
        year, month, day, pre = match.groups()
        version = f'{year}.{month:0>2}.{day:0>2}{pre}'
    return version


async def get_latest_version():
    """
    Return the version of the latest release

    :raise RequestError: if getting the latest version fails
    """
    url = _INFO_URL_PATTERN.format(project_name=__project_name__)
    response = await http.get(url, cache=True, max_cache_age=_MAX_CACHE_AGE)
    all_versions = tuple(response.json()['releases'])
    # PyPI should return the releases sorted by release date (latest last)
    if all_versions:
        return _fix_version(all_versions[-1])


async def get_update_message():
    from packaging import version
    latest = await get_latest_version()
    current = __version__
    msg = f'Latest {__project_name__} version: {latest}'

    latest_parsed = version.parse(latest)
    current_parsed = version.parse(current)
    if current_parsed.is_prerelease:
        if latest_parsed > current_parsed:
            return msg
    elif not latest_parsed.is_prerelease:
        if latest_parsed > current_parsed:
            return msg
