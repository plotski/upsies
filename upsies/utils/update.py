"""
Find most recent version
"""

import re

from packaging.version import parse as parse_version

from .. import __project_name__, __version__
from . import http

import logging  # isort:skip
_log = logging.getLogger(__name__)


_PYPI_URL = f'https://pypi.org/pypi/{__project_name__}/json'
_REPO_URL = ('https://raw.githubusercontent.com/'
             f'plotski/{__project_name__}/master/{__project_name__}/__init__.py')
_MAX_CACHE_AGE = 12 * 3600  # 12 hours
_REQUEST_TIMEOUT = 3


def _fix_version(version):
    match = re.search(r'^(\d{4})\.(\d+)\.(\d+)(.*)$', version)
    if match:
        year, month, day, pre = match.groups()
        version = f'{year}.{month:0>2}.{day:0>2}{pre}'
    return version


async def get_latest_version():
    """
    Return the latest version

    If the current version is a prerelease, get the latest version from source
    code in the repository (e.g. GitHub).

    If the current version is a stable release, get the latest version from the
    package index (e.g. PyPI).

    :raise RequestError: if getting the latest version fails
    """
    if parse_version(__version__).is_prerelease:
        return await _get_latest_prerelease_version()
    else:
        return await _get_latest_release_version()

async def _get_latest_release_version():
    response = await http.get(
        url=_PYPI_URL,
        timeout=_REQUEST_TIMEOUT,
        cache=True,
        max_cache_age=_MAX_CACHE_AGE,
    )
    all_versions = tuple(response.json()['releases'])
    # PyPI should return the releases sorted by release date (latest last)
    if all_versions:
        return _fix_version(all_versions[-1])

async def _get_latest_prerelease_version():
    response = await http.get(
        url=_REPO_URL,
        timeout=_REQUEST_TIMEOUT,
        cache=True,
        max_cache_age=_MAX_CACHE_AGE,
    )
    match = re.search(r'^__version__\s*=\s*[\'"]([\w\.]+)[\'"]', response, flags=re.MULTILINE)
    if match:
        return match.group(1)


async def get_update_message():
    latest = await get_latest_version()
    current = __version__
    msg = f'Latest {__project_name__} version: {latest}'
    latest_parsed = parse_version(latest)
    current_parsed = parse_version(current)
    if current_parsed.is_prerelease:
        if latest_parsed > current_parsed:
            return msg
    elif not latest_parsed.is_prerelease:
        if latest_parsed > current_parsed:
            return msg
