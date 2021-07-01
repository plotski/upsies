"""
HTTP methods with caching
"""

import asyncio
import collections
import hashlib
import io
import json
import os

import httpx

from .. import __project_name__, __version__, constants, errors
from . import fs, html

import logging  # isort:skip
_log = logging.getLogger(__name__)

_default_headers = {
    'Accept-Language': 'en-US,en;q=0.5',
    'User-Agent': f'{__project_name__}/{__version__}',
}

# Use one Lock per requested url + parameters so we can make multiple identical
# requests concurrently without bugging the server.
_request_locks = collections.defaultdict(lambda: asyncio.Lock())

_client = httpx.AsyncClient(
    timeout=60,
)


cache_directory = None
"""
Where to store cached requests

If this is set to a falsy value, default to :attr:`~.constants.CACHE_DIRPATH`.
"""


def close():
    """Close the client session"""
    _log.debug('Closing client: %r', _client)
    asyncio.get_event_loop().run_until_complete(_client.aclose())
    _log.debug('Closed client: %r', _client)


async def get(url, headers={}, params={}, auth=None,
              cache=False, user_agent=False, allow_redirects=True):
    """
    Perform HTTP GET request

    :param str url: URL to request
    :param dict headers: Custom headers (added to default headers)
    :param dict params: Query arguments, e.g. `{"k": "v"} → http://foo/bar?k=v`
    :param auth: Basic access authentication; sequence of <username> and
        <password> or `None`
    :param bool cache: Whether to use cached response if available
    :param bool user_agent: Whether to send the User-Agent header
    :param bool allow_redirects: Whether to follow redirects

    :return: Response text
    :rtype: Response
    :raise RequestError: if the request fails for any expected reason
    """
    return await _request(
        method='GET',
        url=url,
        headers=headers,
        params=params,
        auth=auth,
        cache=cache,
        user_agent=user_agent,
        allow_redirects=allow_redirects,
    )

async def post(url, headers={}, data={}, files={}, auth=None,
               cache=False, user_agent=False, allow_redirects=True):
    """
    Perform HTTP POST request

    :param str url: URL to request
    :param dict headers: Custom headers (added to default headers)
    :param dict data: Data to send as application/x-www-form-urlencoded
    :param dict files: Files to send as multipart/form-data as a dictionary that
        maps field names to file paths or dictionaries. For dictionaries, these
        keys are used:

             ``file``
                 File path or file-like object, e.g. return value of
                 :func:`open` or :class:`~.io.BytesIO`.

             ``filename`` (optional)
                 Name of the file that is reported to the server. Defaults to
                 :func:`~.os.path.basename` of ``file`` if ``file`` is a string,
                 `None` otherwise.

             ``mimetype`` (optional)
                 MIME type of the file content. If not provided and `file` is a
                 string, guess based on extension of ``file``. If `None`, do not
                 send any MIME type.

        Examples:

        >>> files = {
        >>>     "image": "path/to/foo.jpg",
        >>>     "document": {
        >>>         "file": "path/to/bar",
        >>>         "filename": "something.txt",
        >>>         "mimetype": "text/plain",
        >>>     },
        >>>     "data": {
        >>>         "file": io.BytesIO(b'binary data'),
        >>>         "mimetype": "application/octet-stream",
        >>>      },
        >>> })
    :param auth: Basic access authentication; sequence of <username> and
        <password> or `None`
    :param bool cache: Whether to use cached response if available
    :param bool user_agent: Whether to send the User-Agent header
    :param bool allow_redirects: Whether to follow redirects

    :return: Response text
    :rtype: Response
    :raise RequestError: if the request fails for any expected reason
    """
    return await _request(
        method='POST',
        url=url,
        headers=headers,
        data=data,
        files=files,
        auth=auth,
        cache=cache,
        user_agent=user_agent,
        allow_redirects=allow_redirects,
    )

async def download(url, filepath, *args, **kwargs):
    """
    Write downloaded data to file

    :param url: Where to download the data from
    :param filepath: Where to save the downloaded data

    Any other arguments are passed to :func:`get`, except for `cache`, which is
    always `False`.

    If `filepath` exists, no request is made.

    :raise RequestError: if anything goes wrong
    :return: `filepath`
    """
    kwargs['cache'] = False
    if not os.path.exists(filepath):
        _log.debug('Downloading %r to %r', url, filepath)
        response = await get(url, *args, **kwargs)
        try:
            with open(filepath, 'wb') as f:
                f.write(response.bytes)
        except OSError as e:
            if e.strerror:
                raise errors.RequestError(f'Unable to write {filepath}: {e.strerror}')
            else:
                raise errors.RequestError(f'Unable to write {filepath}: {e}')
    else:
        _log.debug('Already downloaded %r to %r', url, filepath)
    return filepath


class Result(str):
    """
    Response to an HTTP request

    This is a subclass of :class:`str` with additional attributes and methods.
    """

    def __new__(cls, text, bytes, headers={}, status_code=None):
        obj = super().__new__(cls, text)
        obj._bytes = bytes
        obj._headers = headers
        obj._status_code = status_code
        return obj

    @property
    def headers(self):
        """HTTP headers"""
        return self._headers

    @property
    def status_code(self):
        """HTTP status code"""
        return self._status_code

    @property
    def bytes(self):
        """Response data as :class:`bytes`"""
        return self._bytes

    def json(self):
        """
        Parse the response text as JSON

        :return: JSON as a `dict`
        :raise Requesterror: if parsing fails
        """
        try:
            return json.loads(self)
        except ValueError as e:
            raise errors.RequestError(f'Malformed JSON: {str(self)}: {e}')

    def __repr__(self):
        return (f'{type(self).__name__}('
                f'text={str(self)!r}, '
                f'bytes={self.bytes!r}, '
                f'headers={self.headers!r}, '
                f'status_code={self.status_code!r})')


async def _request(method, url, headers={}, params={}, data={}, files={},
                   allow_redirects=True, cache=False, auth=None, user_agent=False):
    if method.upper() not in ('GET', 'POST'):
        raise ValueError(f'Invalid method: {method}')

    if isinstance(data, (bytes, str)):
        build_request_args = {'content': data}
    else:
        build_request_args = {'data': data}

    headers = {**_default_headers, **headers}
    request = _client.build_request(
        method=str(method),
        headers=headers,
        url=str(url),
        params=params,
        files=_open_files(files),
        **build_request_args,
    )

    if isinstance(user_agent, str):
        request.headers['User-Agent'] = user_agent
    elif not user_agent:
        del request.headers['User-Agent']

    # Block when requesting the same URL simultaneously
    request_lock_key = (request.url, await request.aread())
    # _log.debug('Request lock key: %r', request_lock_key)
    request_lock = _request_locks[request_lock_key]
    async with request_lock:
        if cache:
            cache_file = _cache_file(method, url, params)
            result = _from_cache(cache_file)
            if result is not None:
                return result

        _log.debug('%s: %r: %r', method, url, params)
        try:
            response = await _client.send(
                request=request,
                auth=auth,
                allow_redirects=allow_redirects,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                raise errors.RequestError(
                    f'{url}: {html.as_text(response.text)}',
                    url=url,
                    text=response.text,
                    headers=response.headers,
                    status_code=response.status_code,
                )
        except httpx.TimeoutException:
            raise errors.RequestError(f'{url}: Timeout')
        except httpx.HTTPError as e:
            _log.debug(f'Unexpected HTTP error: {e!r}')
            raise errors.RequestError(f'{url}: {e}')
        else:
            if cache:
                cache_file = _cache_file(method, url, params)
                _to_cache(cache_file, response.content)
            return Result(
                text=response.text,
                bytes=response.content,
                headers=response.headers,
                status_code=response.status_code,
            )


def _open_files(files):
    """
    Open files for upload

    See :func:`post` and
    https://www.python-httpx.org/advanced/#multipart-file-encoding.

    :raise RequestError: if a file cannot be opened
    """
    opened = {}
    for fieldname, fileinfo in files.items():
        if isinstance(fileinfo, str):
            filename = os.path.basename(fileinfo)
            fileobj = _get_file_object(fileinfo)
            opened[fieldname] = (filename, fileobj)

        elif isinstance(fileinfo, collections.abc.Mapping):
            if isinstance(fileinfo['file'], str):
                filename = fileinfo.get('filename', os.path.basename(fileinfo['file']))
                fileobj = _get_file_object(fileinfo['file'])
            elif isinstance(fileinfo['file'], io.IOBase):
                filename = fileinfo.get('filename', None)
                fileobj = fileinfo['file']
            else:
                raise RuntimeError(f'Invalid "file" value in fileinfo: {fileinfo["file"]!r}')
            mimetype = fileinfo.get('mimetype', False)
            if mimetype is False:
                opened[fieldname] = (filename, fileobj)
            else:
                opened[fieldname] = (filename, fileobj, mimetype)

        else:
            raise RuntimeError(f'Invalid fileinfo: {fileinfo}')

    return opened

def _get_file_object(filepath):
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


def _to_cache(cache_file, bytes):
    try:
        fs.mkdir(fs.dirname(cache_file))
        with open(cache_file, 'wb') as f:
            f.write(bytes)
    except OSError as e:
        raise RuntimeError(f'Unable to write cache file {cache_file}: {e}')


def _from_cache(cache_file):
    bytes = _read_bytes_from_file(cache_file)
    text = _read_string_from_file(cache_file)
    if bytes and text:
        return Result(text=text, bytes=bytes)


def _read_string_from_file(filepath):
    bytes = _read_bytes_from_file(filepath)
    if bytes:
        return str(bytes, encoding='utf-8', errors='replace')


def _read_bytes_from_file(filepath):
    try:
        with open(filepath, 'rb') as f:
            return f.read()
    except OSError:
        pass


def _cache_file(method, url, params={}):
    def make_filename(method, url, params_str):
        if params_str:
            filename = f'{method.upper()}.{url}?{params_str}'
        else:
            filename = f'{method.upper()}.{url}'
        return filename.replace(' ', '+')

    if params:
        params_str = '&'.join((f'{k}={v}' for k,v in params.items()))
        if len(make_filename(method, url, params_str)) > 250:
            params_str = f'[HASH:{_semantic_hash(params)}]'
    else:
        params_str = ''

    return os.path.join(
        cache_directory or constants.CACHE_DIRPATH,
        fs.sanitize_filename(make_filename(method, url, params_str)),
    )


def _semantic_hash(obj):
    """
    Return hash for `obj` that stays the same between sessions

    https://github.com/schollii/sandals/blob/master/json_sem_hash.py
    """
    def as_str(obj):
        if isinstance(obj, collections.abc.Mapping):
            return {as_str(k): as_str(obj[k]) for k in sorted(obj.keys())}
        elif isinstance(obj, str):
            return str(obj)
        elif isinstance(obj, collections.abc.Sequence):
            return [as_str(val) for val in sorted(obj)]
        else:
            return str(obj)

    return hashlib.sha256(bytes(repr(as_str(obj)), 'UTF-8')).hexdigest()
