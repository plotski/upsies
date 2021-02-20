from unittest.mock import Mock, call

import pytest

from upsies.utils.scene import base


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def testdb():
    class TestDb(base.SceneDbApiBase):
        name = 'scn'
        label = 'SCN'
        _search = AsyncMock()
        release_files = AsyncMock()

    return TestDb()


@pytest.mark.asyncio
async def test_search_delegates_query(testdb, mocker):
    query_mock = Mock(search=AsyncMock(return_value=['foo', 'bar', 'baz']))
    only_existing_releases_mock = 'only_existing_releases value'
    results = await testdb.search(
        query=query_mock,
        only_existing_releases=only_existing_releases_mock,
    )
    assert query_mock.search.call_args_list == [call(
        testdb._search,
        only_existing_releases=only_existing_releases_mock,
    )]
    assert results == ['foo', 'bar', 'baz']
