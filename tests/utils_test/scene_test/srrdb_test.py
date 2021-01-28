from unittest.mock import Mock, call

import pytest

from upsies.utils.scene import srrdb


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

@pytest.fixture
def api():
    return srrdb.SrrDbApi()


def test_name():
    assert srrdb.SrrDbApi.name == 'srrdb'


def test_label():
    assert srrdb.SrrDbApi.label == 'srrDB'


@pytest.mark.asyncio
async def test_search_without_group(api, mocker):
    response = {'results': [{'release': 'Foo'}]}
    get_json_mock = mocker.patch('upsies.utils.scene.common.get_json',
                                 AsyncMock(return_value=response))
    response = await api.search('foo', 'bar')
    assert response == ['Foo']
    assert get_json_mock.call_args_list == [
        call(f'{api._search_url}/foo/bar', cache=True),
    ]

@pytest.mark.asyncio
async def test_search_with_group(api, mocker):
    response = {'results': [{'release': 'Foo'}]}
    get_json_mock = mocker.patch('upsies.utils.scene.common.get_json',
                                 AsyncMock(return_value=response))
    await api.search('foo', 'bar', group='BAZ')
    assert get_json_mock.call_args_list == [
        call(f'{api._search_url}/foo/bar/group:BAZ', cache=True),
    ]
