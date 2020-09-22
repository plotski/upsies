import asyncio
import builtins
import collections
import json
import os

import imdbpie

from ....utils import fs

import logging  # isort:skip
_log = logging.getLogger(__name__)


async def _async_imdbpie(method, id):
    def func():
        value = getattr(imdbpie.Imdb(), f'get_{method}')(id)
        return value

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func)


_request_lock = collections.defaultdict(lambda: asyncio.Lock())

async def get_info(id, key='title'):
    # By using one Lock per requested information, we can savely call this
    # method multiple times concurrently without downloading the same data more
    # than once.
    request_lock_key = (id, key, builtins.id(asyncio.get_event_loop()))
    async with _request_lock[request_lock_key]:
        cache_file = os.path.join(fs.tmpdir(), f'imdb.{id}.{key}.json')

        # Try to read info from cache
        try:
            with open(cache_file, 'r') as f:
                return json.loads(f.read())
        except (OSError, ValueError):
            pass

        # Make API request and return empty dict on failure
        try:
            info = await _async_imdbpie(key, id)
        except (LookupError, imdbpie.exceptions.ImdbAPIError) as e:
            _log.debug('IMDb error: %r', e)
            info = {}

        # Cache info unless the request failed
        if info:
            try:
                with open(cache_file, 'w') as f:
                    f.write(json.dumps(info))
            except OSError:
                pass

        return info
