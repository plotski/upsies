from unittest.mock import Mock, call

import pytest

from upsies.utils.webdbs.base import WebDbApiBase


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
    cast = AsyncMock()
    countries = AsyncMock()
    keywords = AsyncMock()
    summary = AsyncMock()
    title_english = AsyncMock()
    title_original = AsyncMock()
    type = AsyncMock()
    year = AsyncMock()


@pytest.fixture
def webdb():
    return TestApi()


def test__attributes(webdb):
    assert webdb.name == 'foo'
    assert webdb.label == 'Foo'


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
