import pytest

from upsies.tools.webdbs import Query, imdb


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
        ('tt1127715', '', 'Sin nombre'),
        ('tt0104684', 'Hard Boiled', 'Lat sau san taam'),
        ('tt0102984', '', 'Stone Cold'),
        ('tt0280990', 'The Nest', 'Nid de guêpes'),
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
    argnames=('query', 'exp_result'),
    argvalues=(
        (Query('Elephant', year='1989'),
         {'title': 'Elephant', 'year': '1989', 'director': 'Alan Clarke'}),
        (Query('The Gift', type='movie', year='2015'),
         {'title': 'The Gift', 'year': '2015', 'director': 'Joel Edgerton'}),
    ),
    ids=lambda value: str(value),
)
async def test_search(query, exp_result, store_response):
    results = await imdb.search(query)
    for r in results:
        print(r)
    print('Expected result:', exp_result)

    def match(result):
        print('Result:', result)
        for k, v in exp_result.items():
            if getattr(result, k) != v:
                return False
        return True

    assert any(match(r) for r in results), results
