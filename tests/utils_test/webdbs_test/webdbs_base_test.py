from unittest.mock import Mock, call

import pytest

from upsies.utils.webdbs.base import WebDbApiBase
from upsies.utils.webdbs.common import Query


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


class TestApi(WebDbApiBase):
    name = 'foo'
    label = 'Foo'
    search = AsyncMock()

    directors = AsyncMock()
    creators = AsyncMock()
    cast = AsyncMock()
    countries = AsyncMock()
    keywords = AsyncMock()
    poster_url = AsyncMock()
    rating_min = 0.0
    rating_max = 10.0
    rating = AsyncMock()
    summary = AsyncMock()
    title_english = AsyncMock()
    title_original = AsyncMock()
    type = AsyncMock()
    url = AsyncMock()
    year = AsyncMock()


@pytest.fixture
def webdb():
    return TestApi()


def test_attributes(webdb):
    assert webdb.name == 'foo'
    assert webdb.label == 'Foo'


def test_sanitize_query(webdb):
    q = Query('The Foo', type='movie', year='2000')
    assert webdb.sanitize_query(q) == q
    with pytest.raises(TypeError, match=r'^Not a Query instance: 123$'):
        webdb.sanitize_query(123)


@pytest.mark.asyncio
async def test_gather(webdb):
    webdb.cast.return_value = 'mock cast'
    webdb.keywords.return_value = ['mock genre one', 'mock genre two']
    webdb.summary.return_value = 'mock summary'
    webdb.title_english.return_value = 'mock title_english'
    webdb.title_original.return_value = 'mock title_original'
    webdb.type.return_value = 'mock type'
    webdb.year.return_value = 'mock year'
    assert await webdb.gather('mock id', 'type', 'year', 'cast', 'keywords') == {
        'cast': 'mock cast',
        'id': 'mock id',
        'keywords': ['mock genre one', 'mock genre two'],
        'type': 'mock type',
        'year': 'mock year',
    }
    assert webdb.cast.call_args_list == [call('mock id')]
    assert webdb.countries.call_args_list == []
    assert webdb.summary.call_args_list == []
    assert webdb.title_english.call_args_list == []
    assert webdb.title_original.call_args_list == []
    assert webdb.type.call_args_list == [call('mock id')]
    assert webdb.year.call_args_list == [call('mock id')]
