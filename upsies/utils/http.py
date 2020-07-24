import asyncio
import collections
import os

import aiohttp
import yarl

from .. import errors
from . import fs

import logging  # isort:skip
_log = logging.getLogger(__name__)


headers = {
    'Accept-Language' : 'en-US,en;q=0.5',
}
_cookiejars = collections.defaultdict(lambda: aiohttp.CookieJar())

def _session(domain):
    _log.debug('Cookies for %s: %r', domain, _cookiejars[domain])
    return aiohttp.ClientSession(
        headers=headers,
        skip_auto_headers=('User-Agent',),
        raise_for_status=True,
        timeout=aiohttp.ClientTimeout(total=30),
        cookie_jar=_cookiejars[domain],
    )


# Use one Lock per requested url + parameters so we can make multiple identical
# requests concurrently without bugging the server.
_request_lock = collections.defaultdict(lambda: asyncio.Lock())


async def get(url, params={}, cache=False):
    """
    Perform HTTP GET request

    :param dict params: Query arguments
    :param bool cache: Whether to use cached response

    :return: Response text
    :rtype: str
    """
    try:
        url = yarl.URL(url)
    except (ValueError, TypeError) as e:
        raise errors.RequestError(f'{url}: {e}')

    request_lock_key = (url, tuple(sorted(params.items())))
    request_lock = _request_lock[request_lock_key]
    # _log.debug('Lock for %r: locked=%r', request_lock_key, request_lock.locked())
    async with request_lock:
        cache_file = _cache_file(url, params)
        _log.debug('Cache file for %r is %r', (url, params), cache_file)
        if cache:
            response = _from_cache(cache_file)
            if response is not None:
                return response

        _log.debug('GET: %r: %r', url, params)
        async with _session(url.host) as session:
            try:
                async with session.get(str(url), params=params) as response:
                    text = await response.text()
            except aiohttp.ClientResponseError as e:
                raise errors.RequestError(f'{url}: {e.message}')
            except aiohttp.ClientConnectionError:
                raise errors.RequestError(f'{url}: Failed to connect')
            except aiohttp.ClientError as e:
                raise errors.RequestError(f'{url}: {e}')

        if cache:
            _to_cache(cache_file, text)

        return text


def _cache_file(url, params={}):
    params_str = '&'.join((f'{k}={v}' for k,v in params.items()))
    if params:
        filename = f'{url}?{params_str}'
    else:
        filename = f'{url}'
    filename = filename.replace('/', '_').replace(' ', '+')
    return os.path.join(fs.tmpdir(), filename)

def _from_cache(cache_file):
    try:
        with open(cache_file, 'r') as f:
            data = f.read()
    except OSError:
        return None
    else:
        _log.debug('Read %r', cache_file)
        return data

def _to_cache(cache_file, string):
    try:
        with open(cache_file, 'w') as f:
            f.write(string)
    except OSError as e:
        raise RuntimeError(f'Unable to write cache file {cache_file}: {e}')
    else:
        _log.debug('Wrote %r', cache_file)
