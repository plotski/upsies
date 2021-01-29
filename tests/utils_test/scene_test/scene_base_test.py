from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.scene import base


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
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

    return TestDb()


@pytest.mark.asyncio
async def test_search_delegates_arguments(testdb, mocker):
    mocker.patch.object(testdb, '_normalize_query', Mock(return_value='mock query'))
    mocker.patch.object(testdb, '_search', AsyncMock(return_value='mock results'))
    mocker.patch.object(testdb, '_normalize_results', Mock(return_value='mock normalized results'))
    results = await testdb.search('foo', group='bar', cache='baz')
    assert testdb._normalize_query.call_args_list == [call(('foo',))]
    assert testdb._search.call_args_list == [call(query='mock query', group='bar', cache='baz')]
    assert testdb._normalize_results.call_args_list == [call('mock results')]
    assert results == 'mock normalized results'

@pytest.mark.asyncio
async def test_search_handles_RequestError(testdb, mocker):
    mocker.patch.object(testdb, '_normalize_query', Mock(return_value='mock query'))
    mocker.patch.object(testdb, '_search', AsyncMock(side_effect=errors.RequestError('no')))
    mocker.patch.object(testdb, '_normalize_results')
    with pytest.raises(errors.SceneError, match=rf'^no$'):
        await testdb.search('foo', group='bar', cache='baz')
    assert testdb._normalize_query.call_args_list == [call(('foo',))]
    assert testdb._search.call_args_list == [call(query='mock query', group='bar', cache='baz')]
    assert testdb._normalize_results.call_args_list == []


def test_normalize_query(testdb):
    assert testdb._normalize_query(('foo  bar ', ' baz')) == ['foo', 'bar', 'baz']


def test_normalize_results(testdb):
    assert testdb._normalize_results(('Foo', 'bar', 'BAZ')) == ['bar', 'BAZ', 'Foo']
