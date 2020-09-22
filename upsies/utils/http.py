import asyncio
import collections
import hashlib
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


async def _request(method, url, params={}, cache=False):
    """
    Perform HTTP request

    :param str method: "POST" or "GET" (case-insensitive)
    :param dict params: Query arguments
    :param bool cache: Whether to use cached response

    :return: Response text
    :rtype: str
    """
    method = method.upper()
    assert method in ('POST', 'GET'), repr(method)

    try:
        url = yarl.URL(url)
    except (ValueError, TypeError) as e:
        raise errors.RequestError(f'{url}: {e}')

    request_lock_key = (url, tuple(sorted(params.items())), id(asyncio.get_event_loop()))
    request_lock = _request_lock[request_lock_key]
    async with request_lock:
        cache_file = _cache_file(url, method, params)
        _log.debug('Cache file for %r is %r', (url, params), cache_file)
        if cache:
            response = _from_cache(cache_file)
            if response is not None:
                return response

        _log.debug('%s: %r: %r', method, url, params)
        async with _session(url.host) as session:
            method_cm = getattr(session, method.lower())  # session.get/post
            try:
                async with method_cm(str(url), params=params) as response:
                    text = await response.text()
            except aiohttp.ClientResponseError as e:
                raise errors.RequestError(f'{url}: {e.message}')
            except aiohttp.ClientError as e:
                raise errors.RequestError(f'{url}: {e}')

        if cache:
            _to_cache(cache_file, text)

        return text


async def get(url, params={}, cache=False):
    """
    Perform HTTP GET request

    :param dict params: Query arguments
    :param bool cache: Whether to use cached response

    :return: Response text
    :rtype: str
    """
    return await _request('GET', url, params=params, cache=cache)


async def post(url, params={}, cache=False):
    """
    Perform HTTP POST request

    :param dict params: Query arguments
    :param bool cache: Whether to use cached response

    :return: Response text
    :rtype: str
    """
    return await _request('POST', url, params=params, cache=cache)


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

def _cache_file(url, method, params={}):
    def make_filename(url, method, params_str):
        if params_str:
            filename = f'{method.upper()}.{url}?{params_str}'
        else:
            filename = f'{method.upper()}.{url}'
        return filename.replace('/', '_').replace(' ', '+')

    if params:
        params_str = '&'.join((f'{k}={v}' for k,v in params.items()))
        if len(make_filename(url, method, params_str)) > 250:
            params_str = f'[HASH:{_semantic_hash(params)}]'
    else:
        params_str = ''

    return os.path.join(
        fs.tmpdir(),
        make_filename(url, method, params_str),
    )

def _semantic_hash(obj):
    """
    Return hash for `obj` that stays the same between sessions

    https://github.com/schollii/sandals/blob/master/json_sem_hash.py
    """
    def sorted_dict_str(obj):
        if isinstance(obj, collections.abc.Mapping):
            return {k: sorted_dict_str(obj[k]) for k in sorted(obj.keys())}
        elif isinstance(obj, str):
            return str(obj)
        elif isinstance(obj, collections.abc.Sequence):
            return [sorted_dict_str(val) for val in obj]
        else:
            return str(obj)

    return hashlib.sha256(bytes(repr(sorted_dict_str(obj)), 'UTF-8')).hexdigest()
