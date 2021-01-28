from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.scene import predb


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

@pytest.fixture
def api():
    return predb.PreDbApi()


def test_name():
    assert predb.PreDbApi.name == 'predb'


def test_label():
    assert predb.PreDbApi.label == 'PreDB'


@pytest.mark.asyncio
async def test_search_without_group(api, mocker):
    response = {
        'status': 'success',
        'data': {'rows': [{'name': 'Foo'}]},
    }
    get_json_mock = mocker.patch('upsies.utils.scene.common.get_json',
                                 AsyncMock(return_value=response))
    response = await api.search('foo', 'bar')
    assert response == ['Foo']
    assert get_json_mock.call_args_list == [
        call(api._search_url, params={'q': 'foo bar'}, cache=True),
    ]

@pytest.mark.asyncio
async def test_search_with_group(api, mocker):
    response = {
        'status': 'success',
        'data': {'rows': [{'name': 'Foo'}]},
    }
    get_json_mock = mocker.patch('upsies.utils.scene.common.get_json',
                                 AsyncMock(return_value=response))
    await api.search('foo', 'bar', group='BAZ')
    assert get_json_mock.call_args_list == [
        call(api._search_url, params={'q': 'foo bar @team BAZ'}, cache=True),
    ]

@pytest.mark.asyncio
async def test_search_with_error_status(api, mocker):
    response = {
        'status': 'error',
        'message': 'Something bad',
        'data': None,
    }
    mocker.patch('upsies.utils.scene.common.get_json',
                 AsyncMock(return_value=response))
    with pytest.raises(errors.SceneError, match=rf'^{api.label}: Something bad$'):
        await api.search('foo', 'bar')
