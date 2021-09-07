"""
Find most recent version
"""

import asyncio
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


async def get_newer_version():
    """
    Return the newest version if there is one

    If the current version is a prerelease, the return value may also be a
    prerelease.

    If the current version is a regular release, the returned version is also a
    regular release.

    :raise RequestError: if getting the latest version fails
    """
    current, release, prerelease = await _get_versions()
    current_parsed = parse_version(current)
    if current_parsed.is_prerelease:
        # Find newest release or prerelease, whichever is newer. Don't return
        # the parsed version because it removes padding zeros ("2021.06.20" ->
        # "2021.6.20").
        version_map = {
            parse_version(release): release,
            parse_version(prerelease): prerelease,
        }
        newest_parsed = sorted(version_map)[-1]
        if newest_parsed > current_parsed:
            return version_map[newest_parsed]
    else:
        if parse_version(release) > current_parsed:
            return release


async def _get_versions():
    current = __version__
    current_parsed = parse_version(current)
    if current_parsed.is_prerelease:
        gathered = await asyncio.gather(_get_latest_release(),
                                        _get_latest_prerelease())
        release, prerelease = gathered
        return current, release, prerelease
    else:
        release = await _get_latest_release()
        return current, release, None


async def _get_latest_release():
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


async def _get_latest_prerelease():
    response = await http.get(
        url=_REPO_URL,
        timeout=_REQUEST_TIMEOUT,
        cache=True,
        max_cache_age=_MAX_CACHE_AGE,
    )
    match = re.search(r'^__version__\s*=\s*[\'"]([\w\.]+)[\'"]', response, flags=re.MULTILINE)
    if match:
        return match.group(1)


def _fix_version(version):
    match = re.search(r'^(\d{4})\.(\d+)\.(\d+)(.*)$', version)
    if match:
        year, month, day, pre = match.groups()
        version = f'{year}.{month:0>2}.{day:0>2}{pre}'
    return version
