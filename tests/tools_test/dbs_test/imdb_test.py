import pytest

from upsies.tools.dbs import Query, imdb


@pytest.mark.asyncio
async def test_summary(store_response):
    assert 'Luke Skywalker' in await imdb.summary('tt0076759')

@pytest.mark.asyncio
async def test_year(store_response):
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
        ('tt1127715', 'Without Name', 'Sin nombre'),
        ('tt0104684', 'Hard Boiled', 'Lat sau san taam'),
    ),
)
async def test_title_original_english(id, english, original, store_response):
    assert await imdb.title_english(id) == english
    assert await imdb.title_original(id) == original

@pytest.mark.asyncio
@pytest.mark.parametrize(
    argnames=('id', 'exp_type'),
    argvalues=(
        ('tt0076759', 'movie'),    # "movie"
        ('tt0192802', 'movie'),    # "tvMovie"
        ('tt2372162', 'season'),   # "tvSeries"
        ('tt1453159', 'season'),   # "tvMiniSeries"
        ('tt5440238', 'episode'),  # "tvEpisode"
    ),
)
async def test_type(id, exp_type, store_response):
    assert await imdb.type(id) == exp_type


@pytest.mark.asyncio
@pytest.mark.parametrize(
    argnames=('id', 'exp_country'),
    argvalues=(
        ('tt0076759', 'United States'),  # Star Wars
        ('tt2209300', 'Poland'),         # Poklosie
        ('tt3286052', 'Canada'),         # February
    ),
)
async def test_country(id, exp_country, store_response):
    assert await imdb.country(id) == exp_country


@pytest.mark.asyncio
@pytest.mark.parametrize(
    argnames=('query', 'exp_year'),
    argvalues=(
        (Query('The Gift', type='movie', year='2015'), '2015'),
    ),
    ids=lambda value: str(value),
)
async def test_search_year(query, exp_year, store_response):
    results = await imdb.search(query)
    for result in results:
        assert result.year == exp_year, result
