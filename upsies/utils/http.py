"""
HTTP methods with caching
"""

import asyncio
import builtins
import collections
import http
import io
import json
import os
import pathlib
import time

import httpx

from .. import __project_name__, __version__, constants, errors
from . import fs, html, semantic_hash

import logging  # isort:skip
_log = logging.getLogger(__name__)

_default_timeout = 60
_default_headers = {
    'Accept-Language': 'en-US,en;q=0.5',
    'User-Agent': f'{__project_name__}/{__version__}',
}

# Use one Lock per requested url + parameters so we can make multiple identical
# requests concurrently without bugging the server.
_request_locks = collections.defaultdict(lambda: asyncio.Lock())

# Use one single client session for all connections to benefit from re-using
# connections for multiple requests. The downside is that we have to remember to
# close the client before the application terminates.
_client = httpx.AsyncClient(
    timeout=_default_timeout,
    headers=_default_headers,
)


cache_directory = None
"""
Where to store cached responses

If this is set to a falsy value, default to
:attr:`~.constants.DEFAULT_CACHE_DIRECTORY`.
"""

def _get_cache_directory():
    return cache_directory or constants.DEFAULT_CACHE_DIRECTORY


async def close():
    """
    Close the global client session used for all requests

    This coroutine function must be called before the application terminates.
    """
    _log.debug('Closing client: %r', _client)
    await _client.aclose()
    _log.debug('Closed client: %r', _client)


async def get(
        url,
        headers={},
        params={},
        auth=None,
        cache=False,
        max_cache_age=float('inf'),
        user_agent=False,
        follow_redirects=True,
        timeout=_default_timeout,
        cookies=None,
    ):
    """
    Perform HTTP GET request

    :param str url: URL to request
    :param dict headers: Custom headers (added to default headers)
    :param dict params: Query arguments, e.g. `{"k": "v"} → http://foo/bar?k=v`
    :param auth: Basic access authentication; sequence of <username> and
        <password> or `None`
    :param bool cache: Whether to use cached response if available
    :param int,float max_cache_age: Maximum age of cache in seconds
    :param bool user_agent: Whether to send the User-Agent header
    :param bool follow_redirects: Whether to follow redirects
    :param int,float timeout: Maximum number of seconds the request may take
    :param cookies: Cookies to include in the request (merged with
        existing cookies in the global client session)

        * If `cookies` is a :class:`dict`, forget them after the request.

        * If `cookies` is a :class:`str`, load cookies from that path (if it
          exists), perform the request, and save the new set of cookies to the
          same path.

        .. note:: Session cookies are not saved.

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
        max_cache_age=max_cache_age,
        user_agent=user_agent,
        follow_redirects=follow_redirects,
        timeout=timeout,
        cookies=cookies,
    )

async def post(
        url,
        headers={},
        data={},
        files={},
        auth=None,
        cache=False,
        max_cache_age=float('inf'),
        user_agent=False,
        follow_redirects=True,
        timeout=_default_timeout,
        cookies=None,
    ):
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
    :param int,float max_cache_age: Maximum age of cache in seconds
    :param bool user_agent: Whether to send the User-Agent header
    :param bool follow_redirects: Whether to follow redirects
    :param int,float timeout: Maximum number of seconds the request may take
    :param cookies: Cookies to include in the request (merged with existing
        cookies in the global client session); see :func:`get`

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
        max_cache_age=max_cache_age,
        user_agent=user_agent,
        follow_redirects=follow_redirects,
        timeout=timeout,
        cookies=cookies,
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
            msg = e.strerror if e.strerror else str(e)
            raise errors.RequestError(f'Unable to write {filepath}: {msg}')
    else:
        _log.debug('Already downloaded %r to %r', url, filepath)
    return filepath


class Result(str):
    """
    Response to an HTTP request

    This is a subclass of :class:`str` with additional attributes and methods.
    """

    def __new__(cls, text, bytes, headers=None, status_code=None):
        obj = super().__new__(cls, text)
        obj._bytes = bytes
        obj._headers = headers if headers is not None else {}
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
        kwargs = [
            f'text={str(self)!r}',
            f'bytes={self.bytes!r}',
        ]
        if self.headers != {}:
            kwargs.append(f'headers={self.headers!r}')
        if self.status_code is not None:
            kwargs.append(f'status_code={self.status_code!r}')
        return f'{type(self).__name__}({", ".join(kwargs)})'


async def _request(
        method,
        url,
        headers={},
        params={},
        data={},
        files={},
        follow_redirects=True,
        cache=False,
        max_cache_age=float('inf'),
        auth=None,
        user_agent=False,
        timeout=_default_timeout,
        cookies=None,
    ):
    if method.upper() not in ('GET', 'POST'):
        raise ValueError(f'Invalid method: {method}')

    # Create request object
    if isinstance(data, (bytes, str)):
        build_request_args = {'content': data}
    else:
        build_request_args = {'data': data}
    request = _client.build_request(
        method=str(method),
        url=str(url),
        headers={**_default_headers, **headers},
        cookies=_load_cookies(cookies),
        params=params,
        files=_open_files(files),
        timeout=timeout,
        **build_request_args,
    )

    # Adjust User-Agent
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
            result = _from_cache(cache_file, max_age=max_cache_age)
            if result is not None:
                return result

        _log.debug('Sending request: %r', request)
        # _log.debug('Request headers: %r', request.headers)
        # _log.debug('Request data: %r', await request.aread())
        try:
            response = await _client.send(
                request=request,
                auth=auth,
                follow_redirects=follow_redirects,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code not in (301, 302, 303, 307, 308):
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
            if cookies and isinstance(cookies, (str, pathlib.Path)):
                _save_cookies(filepath=cookies, domain=response.url.host)

            if cache:
                cache_file = _cache_file(method, url, params)
                _to_cache(cache_file, response.content)

            # _log.debug('Response content: %r', response.content)
            # _log.debug('Response headers: %r', response.headers)
            return Result(
                text=response.text,
                bytes=response.content,
                headers=response.headers,
                status_code=response.status_code,
            )


def _load_cookies(cookies):
    if cookies:
        _log.debug('Loading cookies from %r', cookies)
    if isinstance(cookies, (collections.abc.Mapping, http.cookiejar.CookieJar)):
        return cookies
    elif cookies and isinstance(cookies, (str, pathlib.Path)):
        filepath_abs = os.path.join(_get_cache_directory(), cookies)
        cookie_jar = http.cookiejar.LWPCookieJar(filepath_abs)
        try:
            cookie_jar.load()
        except FileNotFoundError:
            _log.debug('No such file: %r', filepath_abs)
            pass
        except OSError as e:
            msg = e.strerror if e.strerror else str(e)
            raise errors.RequestError(f'Failed to read {cookie_jar.filename}: {msg}')
        else:
            _log.debug('Loaded cookie jar: %r', cookie_jar)
        return cookie_jar
    elif cookies is not None:
        raise RuntimeError(f'Unsupported cookies type: {cookies!r}')


def _save_cookies(filepath, domain):
    filepath_abs = os.path.join(_get_cache_directory(), filepath)
    _log.debug('Saving cookies for %r to %r', domain, filepath_abs)
    file_cookie_jar = http.cookiejar.LWPCookieJar(filepath_abs)
    for cookie in _client.cookies.jar:
        if cookie.domain.endswith(domain):
            _log.debug('Saving cookie: %r', cookie)
            file_cookie_jar.set_cookie(cookie)
        else:
            _log.debug('Ignoring cookie because %r does not end with %r: %r', cookie.domain, domain, cookie)

    if file_cookie_jar:
        try:
            file_cookie_jar.save()
        except OSError as e:
            msg = e.strerror if e.strerror else str(e)
            raise errors.RequestError(f'Failed to write {filepath_abs}: {msg}')
        else:
            _log.debug('Saved file cookie jar: %r', file_cookie_jar)


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
        msg = e.strerror if e.strerror else 'Failed to open'
        raise errors.RequestError(f'{filepath}: {msg}')


def _to_cache(cache_file, bytes):
    if not isinstance(bytes, builtins.bytes):
        raise TypeError(f'Not a bytes object: {bytes!r}')

    # Try to remove <script> tags
    if b'<script' in bytes:
        try:
            string = str(bytes, encoding='utf-8', errors='strict')
        except UnicodeDecodeError:
            pass
        else:
            string = html.purge_javascript(string)
            bytes = string.encode('utf-8')

    try:
        fs.mkdir(fs.dirname(cache_file))
        with open(cache_file, 'wb') as f:
            f.write(bytes)
    except OSError as e:
        raise RuntimeError(f'Unable to write cache file {cache_file}: {e}')


def _from_cache(cache_file, max_age=float('inf')):
    try:
        cache_mtime = os.stat(cache_file).st_mtime
    except FileNotFoundError:
        return None
    else:
        cache_age = time.time() - cache_mtime
        if cache_age <= max_age:
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
            params_str = f'[HASH:{semantic_hash(params)}]'
    else:
        params_str = ''

    return os.path.join(
        _get_cache_directory(),
        fs.sanitize_filename(make_filename(method, url, params_str)),
    )
