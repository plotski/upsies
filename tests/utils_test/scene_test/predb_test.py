from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.scene import SceneQuery, predb


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


def test_default_config():
    assert predb.PreDbApi.default_config == {}


@pytest.mark.parametrize('group', (None, '', 'ASDF'), ids=lambda v: str(v))
@pytest.mark.asyncio
async def test_search_calls_http_get(group, api, mocker):
    response = Mock(json=Mock(return_value={
        'status': 'success',
        'data': {'rows': [{'name': 'Foo'}]},
    }))
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock(return_value=response))

    keywords = ['foo', 'bar']
    query_string = ' '.join(keywords)
    exp_params = {'count': 1000}
    if group:
        exp_params['q'] = f'{query_string.lower()} @team {group.lower()}'
    else:
        exp_params['q'] = f'{query_string.lower()}'

    response = await api._search(keywords=keywords, group=group)
    assert get_mock.call_args_list == [
        call(api._search_url, params=exp_params, cache=True),
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
    with pytest.raises(errors.RequestError, match=rf'^{api.label}: Something bad$'):
        await api.search(SceneQuery('foo', 'bar'))
