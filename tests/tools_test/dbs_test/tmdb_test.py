import pytest

from upsies.tools.dbs import tmdb
from upsies.tools.dbs.tmdb import _info


@pytest.mark.asyncio
async def test_summary(store_request_cache):
    assert 'Luke Skywalker' in await tmdb.summary('movie/11')

@pytest.mark.asyncio
async def test_year(store_request_cache):
    assert await tmdb.year('movie/11') == '1977'

@pytest.mark.asyncio
async def test_title_original_english(store_request_cache):
    assert await tmdb.title_english('movie/11') == ''
    assert await tmdb.title_original('movie/11') == ''

@pytest.mark.asyncio
async def test_keywords(store_request_cache):
    assert 'space opera' in await _info.keywords('movie/11')

@pytest.mark.asyncio
async def test_cast(store_request_cache):
    assert 'Harrison Ford' in await _info.cast('movie/11')

@pytest.mark.asyncio
async def test_type(store_request_cache):
    with pytest.raises(NotImplementedError, match=r'^Type lookup is not implemented for TMDb$'):
        await tmdb.type(id)
