import pytest

from upsies.tools.dbs import imdb


@pytest.mark.asyncio
async def test_summary(store_request_cache):
    assert 'Luke Skywalker' in await imdb.summary('tt0076759')

@pytest.mark.asyncio
async def test_year(store_request_cache):
    assert await imdb.year('tt0076759') == '1977'

@pytest.mark.asyncio
@pytest.mark.parametrize(
    argnames=('id', 'english', 'original'),
    argvalues=(
        ('tt0076759', 'Star Wars: Episode IV - A New Hope', 'Star Wars'),
        ('tt2209300', 'Aftermath', 'Poklosie'),
        ('tt3286052', "The Blackcoat's Daughter", 'February'),
        ('tt1405737', 'Traffic Light', 'Ramzor'),
        ('tt0080455', '', 'The Blues Brothers'),
    ),
)
async def test_title_original_english(id, english, original, store_request_cache):
    assert await imdb.title_english(id) == english
    assert await imdb.title_original(id) == original
