import json

from ... import errors
from .. import http


async def get_json(url, params=None, cache=True):
    try:
        string = await http.get(url, params=params, cache=cache)
    except errors.RequestError as e:
        raise errors.SceneError(e)
    else:
        try:
            return json.loads(string)
        except (ValueError, TypeError) as e:
            raise errors.SceneError(f'Failed to parse JSON: {e}: {string}')
