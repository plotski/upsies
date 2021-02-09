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


@pytest.mark.parametrize('cache', (True, False), ids=lambda v: str(v))
@pytest.mark.parametrize('group', (None, '', 'ASDF'), ids=lambda v: str(v))
@pytest.mark.asyncio
async def test_search_calls_http_get(group, cache, api, mocker):
    response = Mock(json=Mock(return_value={
        'results': [{'release': 'Foo'}],
    }))
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock(return_value=response))

    keywords = ['foo', 'bar']
    path = '/'.join(keywords).lower()
    if group:
        path += f'/group:{group.lower()}'

    response = await api._search(keywords=keywords, group=group, cache=cache)
    assert get_mock.call_args_list == [
        call(f'{api._search_url}/{path}', cache=True),
    ]
    assert list(response) == ['Foo']
