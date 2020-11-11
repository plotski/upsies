import asyncio
import atexit
import collections
import hashlib
import os

import httpx

from .. import __project_name__, __version__, errors
from . import fs

import logging  # isort:skip
_log = logging.getLogger(__name__)

_headers = {
    'Accept-Language': 'en-US,en;q=0.5',
    'User-Agent': f'{__project_name__}/{__version__}',
}

# Use one Lock per requested url + parameters so we can make multiple identical
# requests concurrently without bugging the server.
_request_locks = collections.defaultdict(lambda: asyncio.Lock())

_client = httpx.AsyncClient(
    timeout=30,
)

def _close_client():
    _log.debug('Closing client: %r', _client)
    asyncio.get_event_loop().run_until_complete(_client.aclose())
    _log.debug('Closed client: %r', _client)
atexit.register(_close_client)


async def get(url, params={}, cache=False, user_agent=False):
    """
    Perform HTTP GET request

    :param str url: URL to request
    :param dict params: Query arguments, e.g. {"k": "v"} -> http://foo/bar?k=v
    :param bool cache: Whether to use cached response if available
    :param bool user_agent: Whether to send the User-Agent header

    :return: Response text
    :rtype: str
    """
    return await _request(
        method='GET',
        url=url,
        params=params,
        cache=cache,
        user_agent=user_agent,
    )

async def post(url, data={}, files={}, cache=False, user_agent=False):
    """
    Perform HTTP POST request

    :param str url: URL to request
    :param dict data: Data to send as application/x-www-form-urlencoded
    :param dict files: Files to send as multipart/form-data
    :param bool cache: Whether to use cached response if available
    :param bool user_agent: Whether to send the User-Agent header

    :return: Response text
    :rtype: str
    """
    return await _request(
        method='POST',
        url=url,
        data=data,
        files=files,
        cache=cache,
        user_agent=user_agent,
    )


async def _request(method, url, params={}, data={}, files={}, cache=False, user_agent=False):
    assert isinstance(user_agent, bool)
    if method.upper() not in ('GET', 'POST'):
        raise ValueError(f'Invalid method: {method}')

    request = _client.build_request(
        method=str(method),
        headers=_headers,
        url=str(url),
        params=params,
        data=data,
        files=_open_files(files),
    )

    if not user_agent:
        del request.headers['User-Agent']

    # Block when requesting the same URL simultaneously
    request_lock_key = (request.url, await request.aread())
    _log.debug('Request lock key: %r', request_lock_key)
    request_lock = _request_locks[request_lock_key]
    async with request_lock:
        if cache:
            cache_file = _cache_file(method, url, params)
            response = _from_cache(cache_file)
            if response is not None:
                _log.debug('Got cached response: %r', response)
                return response
            else:
                _log.debug('No cached response for: %r', request_lock_key)

        _log.debug('%s: %r: %r', method, url, params)
        try:
            response = await _client.send(request)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                raise errors.RequestError(
                    f'{url}: {response.text}',
                    headers=response.headers,
                    status_code=response.status_code,
                )
        except httpx.NetworkError:
            raise errors.RequestError(f'{url}: Failed to connect')
        except httpx.HTTPError as e:
            raise errors.RequestError(f'{url}: {e}')
        else:
            if cache:
                cache_file = _cache_file(method, url, params)
                _log.debug('Writing response to cache: %r', cache_file)
                _to_cache(cache_file, response.text)
            return response.text


def _open_files(files):
    """
    Open files for upload

    :param files: Dictionary that maps field names to file paths or to 2-tuples
        of file paths and MIME types

        Example:

        >>> _open_files({
        >>>     "image": "path/to/foo.jpg",
        >>>     "document": ("path/to/bar", "text/plain"),
        >>> })

    :return: See https://www.python-httpx.org/advanced/#multipart-file-encoding

    :raise RequestError: if a file cannot be opened
    """
    opened = {}
    for fieldname, fileinfo in files.items():
        if isinstance(fileinfo, str):
            opened[fieldname] = (
                os.path.basename(fileinfo),     # File name
                _get_fileobj(fileinfo),         # File handle
            )
        elif isinstance(fileinfo, collections.abc.Sequence) and len(fileinfo) == 2:
            opened[fieldname] = (
                os.path.basename(fileinfo[0]),  # File name
                _get_fileobj(fileinfo[0]),      # File handle
                fileinfo[1],                    # MIME type
            )
        else:
            raise RuntimeError(f'Invalid file: {fileinfo}')
    return opened

def _get_fileobj(filepath):
    """
    Open `filepath` and return the file object

    :raise RequestError: if OSError is raised by `open`
    """
    try:
        return open(filepath, 'rb')
    except OSError as e:
        if e.strerror:
            msg = e.strerror
        else:
            msg = 'Failed to open'
        raise errors.RequestError(f'{filepath}: {msg}')


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

def _cache_file(method, url, params={}):
    def make_filename(method, url, params_str):
        if params_str:
            filename = f'{method.upper()}.{url}?{params_str}'
        else:
            filename = f'{method.upper()}.{url}'
        return filename.replace('/', '_').replace(' ', '+')

    if params:
        params_str = '&'.join((f'{k}={v}' for k,v in params.items()))
        if len(make_filename(method, url, params_str)) > 250:
            params_str = f'[HASH:{_semantic_hash(params)}]'
    else:
        params_str = ''

    return os.path.join(
        fs.tmpdir(),
        make_filename(method, url, params_str),
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
