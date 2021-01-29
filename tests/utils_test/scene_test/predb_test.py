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


@pytest.mark.parametrize('cache', (True, False), ids=lambda v: str(v))
@pytest.mark.parametrize('group', (None, '', 'ASDF'), ids=lambda v: str(v))
@pytest.mark.asyncio
async def test_search_calls_http_get(group, cache, api, mocker):
    response = Mock(json=Mock(return_value={
        'status': 'success',
        'data': {'rows': [{'name': 'Foo'}]},
    }))
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock(return_value=response))

    query = ['foo', 'bar']
    query_string = ' '.join(query)
    if group:
        exp_params = {'q': f'{query_string} @team {group}'}
    else:
        exp_params = {'q': f'{query_string}'}

    response = await api._search(query=query, group=group, cache=cache)
    assert get_mock.call_args_list == [
        call(api._search_url, params=exp_params, cache=cache),
    ]
    assert list(response) == ['Foo']

@pytest.mark.asyncio
async def test_search_handles_error_status(api, mocker):
    response = Mock(json=Mock(return_value={
        'status': 'error',
        'message': 'Something bad',
        'data': None,
    }))
    mocker.patch('upsies.utils.http.get', AsyncMock(return_value=response))
    with pytest.raises(errors.SceneError, match=rf'^{api.label}: Something bad$'):
        await api.search('foo', 'bar')
