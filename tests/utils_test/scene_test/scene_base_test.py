from unittest.mock import AsyncMock, Mock, call

import pytest

from upsies.utils.scene import base


def make_TestDb(default_config=None, **kwargs):
    default_config_ = default_config

    class TestDb(base.SceneDbApiBase):
        name = 'scn'
        label = 'SCN'
        default_config = default_config_ or {}
        _search = AsyncMock()
        release_files = AsyncMock()

    return TestDb(**kwargs)


def test_config_property():
    db = make_TestDb()
    assert db.config == {}
    db = make_TestDb(default_config={'foo': 1, 'bar': 2})
    assert db.config == {'foo': 1, 'bar': 2}
    db = make_TestDb(default_config={'foo': 1, 'bar': 2}, config={'bar': 99})
    assert db.config == {'foo': 1, 'bar': 99}


@pytest.mark.asyncio
async def test_search_delegates_query(mocker):
    query_mock = Mock(search=AsyncMock(return_value=['foo', 'bar', 'baz']))
    only_existing_releases_mock = 'only_existing_releases value'
    db = make_TestDb()
    results = await db.search(
        query=query_mock,
        only_existing_releases=only_existing_releases_mock,
    )
    assert query_mock.search.call_args_list == [call(
        db._search,
        only_existing_releases=only_existing_releases_mock,
    )]
    assert results == ['foo', 'bar', 'baz']
