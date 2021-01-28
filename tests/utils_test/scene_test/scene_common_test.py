from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.scene import common


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.mark.asyncio
async def test_get_json_returns_parsed_json(mocker):
    http_mock = mocker.patch('upsies.utils.scene.common.http',
                             get=AsyncMock(return_value='{"foo": "bar"}'))
    cache = object()
    params = object()
    response = await common.get_json('http://localhost/foo/bar', params=params, cache=cache)
    assert response == {'foo': 'bar'}
    assert http_mock.get.call_args_list == [
        call('http://localhost/foo/bar', params=params, cache=cache),
    ]

@pytest.mark.asyncio
async def test_get_json_catches_RequestError(mocker):
    http_mock = mocker.patch('upsies.utils.scene.common.http',
                             get=AsyncMock(side_effect=errors.RequestError('nay')))
    with pytest.raises(errors.SceneError, match=r'^nay$'):
        await common.get_json('http://localhost/foo/bar')
    assert http_mock.get.call_args_list == [
        call('http://localhost/foo/bar', params=None, cache=True),
    ]

@pytest.mark.parametrize('exc_type', (ValueError, TypeError))
@pytest.mark.asyncio
async def test_get_json_catches_ValueError_from_parsing_json(exc_type, mocker):
    mocker.patch('upsies.utils.scene.common.http',
                 get=AsyncMock(return_value='{"foo": "bar"]'))
    with pytest.raises(errors.SceneError, match=r'^Failed to parse JSON:'):
        await common.get_json('http://localhost/foo/bar')
