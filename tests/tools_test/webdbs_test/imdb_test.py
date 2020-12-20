from unittest.mock import Mock

import pytest

from upsies.tools.webdbs import Query, SearchResult, imdb
from upsies.utils import ReleaseType


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def api():
    return imdb.ImdbApi()


@pytest.mark.asyncio
async def test_search_returns_empty_list_if_title_is_empty(api, store_response):
    assert await api.search(Query('', year='2009')) == []

@pytest.mark.asyncio
async def test_search_returns_list_of_SearchResults(api, store_response):
    results = await api.search(Query('Star Wars'))
    for result in results:
        assert isinstance(result, SearchResult)


@pytest.mark.parametrize(
    argnames=('query', 'exp_top_title'),
    argvalues=(
        (Query('Blues Brothers', year=1980), 'The Blues Brothers'),
        (Query('Blues Brothers', year='1998'), 'Blues Brothers 2000'),
        (Query('Blues Brothers', year=1950), ''),
        (Query('Star Wars', year=2008), 'Star Wars: The Clone Wars'),
        (Query('Star Wars', year=2014), 'Star Wars Rebels'),
        (Query('Star Wars', year=1950), ''),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_for_year(query, exp_top_title, api, store_response):
    results = await api.search(query)
    if exp_top_title:
        assert results[0].title == exp_top_title
    else:
        assert not results

@pytest.mark.parametrize(
    argnames=('query', 'exp_titles'),
    argvalues=(
        (Query('star wars', type=ReleaseType.series), ('Star Wars: Clone Wars', 'Star Wars: The Clone Wars')),
        (Query('rampage', type=ReleaseType.series), ('Road to Rampage', 'Rampage: Killing Without Reason')),
        (Query('balada triste trompeta', type=ReleaseType.series), ()),
        (Query('time traveling bong', type=ReleaseType.series), ('Time Traveling Bong',)),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_for_series(query, exp_titles, api, store_response):
    results = await api.search(query)
    for r in results:
        print(r.title, r.type, r.year)
    titles = [r.title for r in results]
    if exp_titles:
        for exp_title in exp_titles:
            assert exp_title in titles
    else:
        assert not titles

@pytest.mark.parametrize(
    argnames=('query', 'exp_titles'),
    argvalues=(
        (Query('star wars', type=ReleaseType.movie), ('Star Wars: Episode IV - A New Hope', 'Star Wars: Episode I - The Phantom Menace')),
        (Query('rampage', type=ReleaseType.movie), ('Rampage: Capital Punishment', 'American Rampage')),
        (Query('balada triste trompeta', type=ReleaseType.movie), ('The Last Circus',)),
        (Query('time traveling bong', type=ReleaseType.movie), ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_for_movie(query, exp_titles, api, store_response):
    results = await api.search(query)
    for r in results:
        print(r.title, r.type, r.year)
    titles = [r.title for r in results]
    if exp_titles:
        for exp_title in exp_titles:
            assert exp_title in titles
    else:
        assert not titles


@pytest.mark.parametrize(
    argnames=('query', 'exp_cast'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), ('Dan Aykroyd', 'John Belushi')),
        (Query('Deadwood', year=2004), ('Brad Dourif', 'Ian McShane')),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_cast(query, exp_cast, api, store_response):
    results = await api.search(query)
    cast = results[0].cast
    for member in exp_cast:
        assert member in cast

@pytest.mark.parametrize(
    argnames=('query', 'exp_country'),
    argvalues=(
        (Query('star wars', type=ReleaseType.movie, year=1977), 'United States'),
        (Query('balada triste trompeta', type=ReleaseType.movie, year=2010), 'Spain'),
        (Query('The Forest', type=ReleaseType.series, year=2017), 'France'),
        (Query('Karppi', type=ReleaseType.series, year=2018), 'Finland'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_country(query, exp_country, api, store_response):
    results = await api.search(query)
    country = await results[0].country()
    assert country == exp_country

@pytest.mark.parametrize(
    argnames=('query', 'exp_id'),
    argvalues=(
        (Query('Blues Brothers', year=1980), 'tt0080455'),
        (Query('Blues Brothers', year=1998), 'tt0118747'),
        (Query('Star Wars', year=2008), 'tt0458290'),
        (Query('Star Wars', year=2014), 'tt2930604'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_id(query, exp_id, api, store_response):
    results = await api.search(query)
    assert results[0].id == exp_id

@pytest.mark.parametrize(
    argnames=('query', 'exp_director'),
    argvalues=(
        (Query('star wars', type=ReleaseType.movie, year=1977), 'George Lucas'),
        (Query('balada triste trompeta', type=ReleaseType.movie, year=2010), 'Álex de la Iglesia'),
        (Query('The Forest', type=ReleaseType.series, year=2017), ''),
        (Query('Karppi', type=ReleaseType.series, year=2018), ''),

    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_director(query, exp_director, api, store_response):
    results = await api.search(query)
    assert results[0].director == exp_director

@pytest.mark.parametrize(
    argnames=('query', 'exp_keywords'),
    argvalues=(
        (Query('star wars', type=ReleaseType.movie, year=1977), ('action', 'adventure', 'fantasy')),
        (Query('balada triste trompeta', type=ReleaseType.movie, year=2010), ('comedy', 'drama', 'horror')),
        (Query('The Forest', type=ReleaseType.series, year=2017), ('crime', 'drama')),
        (Query('Deadwood', type=ReleaseType.series, year=2004), ('crime', 'drama', 'history')),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_keywords(query, exp_keywords, api, store_response):
    results = await api.search(query)
    if exp_keywords:
        for kw in exp_keywords:
            assert kw in results[0].keywords
    else:
        assert not results[0].keywords

@pytest.mark.parametrize(
    argnames=('query', 'exp_summary'),
    argvalues=(
        (Query('star wars', type=ReleaseType.movie, year=1977), 'Luke Skywalker joins forces with a Jedi'),
        (Query('balada triste trompeta', type=ReleaseType.movie, year=2010), 'A young trapeze artist must decide'),
        (Query('The Forest', type=ReleaseType.series, year=2017), 'Sixteen-year-old Jennifer disappears'),
        (Query('Deadwood', type=ReleaseType.series, year=2004), 'set in the late 1800s'),
        (Query('The Deadwood Coach', type=ReleaseType.movie, year=1924), ''),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_summary(query, exp_summary, api, store_response):
    results = await api.search(query)
    if exp_summary:
        assert exp_summary in results[0].summary
    else:
        assert results[0].summary == ''

@pytest.mark.parametrize(
    argnames=('query', 'exp_top_title'),
    argvalues=(
        (Query('Blues Brothers', year=1980), 'The Blues Brothers'),
        (Query('Blues Brothers', year=1998), 'Blues Brothers 2000'),
        (Query('Star Wars', year=2008), 'Star Wars: The Clone Wars'),
        (Query('Star Wars', year=2014), 'Star Wars Rebels'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_title(query, exp_top_title, api, store_response):
    results = await api.search(query)
    assert results[0].title == exp_top_title

@pytest.mark.parametrize(
    argnames=('query', 'exp_title_english', 'exp_title_original'),
    argvalues=(
        (Query('36th Chamber of Shaolin', type=ReleaseType.movie, year=1978), 'The 36th Chamber of Shaolin', 'Shao Lin san shi liu fang'),
        (Query('Aftermath', type=ReleaseType.movie, year=2012), 'Aftermath', 'Poklosie'),
        (Query('balada triste trompeta', type=ReleaseType.movie, year=2010), 'The Last Circus', 'Balada triste de trompeta'),
        (Query('Blues Brothers', type=ReleaseType.movie, year=1980), '', 'The Blues Brothers'),
        (Query('Cyborg', type=ReleaseType.movie, year=1989), '', 'Cyborg'),
        (Query('Deadwood', type=ReleaseType.series, year=2004), '', 'Deadwood'),
        (Query('February', type=ReleaseType.movie, year=2015), "The Blackcoat's Daughter", 'February'),
        (Query('Hard Boiled', type=ReleaseType.movie, year=1992), 'Hard Boiled', 'Lat sau san taam'),
        (Query('Karppi', type=ReleaseType.series, year=2018), 'Deadwind', 'Karppi'),
        (Query('Olympus Has Fallen', type=ReleaseType.movie, year=2013), '', 'Olympus Has Fallen'),
        (Query('Sin Nombre', type=ReleaseType.movie, year=2009), '', 'Sin nombre'),
        (Query('Star Wars', type=ReleaseType.movie, year=1977), '', 'Star Wars'),
        (Query('Stone Cold', type=ReleaseType.movie, year=1991), '', 'Stone Cold'),
        (Query('The Forest', type=ReleaseType.series, year=2017), 'The Forest', 'La forêt'),
        (Query('The Nest', type=ReleaseType.movie, year=2002), 'The Nest', 'Nid de guêpes'),
        (Query('Traffic Light', type=ReleaseType.series, year=2008), 'Traffic Light', 'Ramzor'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_title_english_original(query, exp_title_english, exp_title_original, api, store_response):
    results = await api.search(query)
    title_english = await results[0].title_english()
    title_original = await results[0].title_original()
    assert title_english == exp_title_english
    assert title_original == exp_title_original

@pytest.mark.parametrize(
    argnames=('query', 'exp_top_type'),
    argvalues=(
        (Query('Blues Brothers', year=1980), ReleaseType.movie),
        (Query('Blues Brothers', year=1998), ReleaseType.movie),
        (Query('Star Wars', year=2008), ReleaseType.series),
        (Query('Star Wars', year=2014), ReleaseType.series),
        (Query('Elephant', year=1989, type=ReleaseType.movie), ReleaseType.movie),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_type(query, exp_top_type, api, store_response):
    results = await api.search(query)
    assert results[0].type == exp_top_type

@pytest.mark.parametrize(
    argnames=('query', 'exp_url'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), 'http://imdb.com/title/tt0080455'),
        (Query('Deadwood', year=2004), 'http://imdb.com/title/tt0348914'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_url(query, exp_url, api, store_response):
    results = await api.search(query)
    assert results[0].url == exp_url

@pytest.mark.parametrize(
    argnames=('query', 'exp_year'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), '1980'),
        (Query('Deadwood', year=2004), '2004'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_year(query, exp_year, api, store_response):
    results = await api.search(query)
    assert results[0].year == exp_year


@pytest.mark.parametrize(
    argnames=('id', 'exp_cast'),
    argvalues=(
        ('tt0080455', ('Dan Aykroyd', 'John Belushi')),      # Blues Brothers
        ('tt0348914', ('Timothy Olyphant', 'Ian McShane')),  # Deadwood
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_cast(id, exp_cast, api, store_response):
    cast = await api.cast(id)
    if exp_cast:
        for member in exp_cast:
            assert member in cast
    else:
        assert not cast

@pytest.mark.parametrize(
    argnames=('id', 'exp_country'),
    argvalues=(
        ('tt0080455', 'United States'),   # Blues Brothers
        ('tt6560040', 'France'),          # The Forest
        ('tt1572491', 'Spain'),           # The Last Circus
        ('tt3286052', 'Canada'),          # February
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_country(id, exp_country, api, store_response):
    country = await api.country(id)
    assert country == exp_country

@pytest.mark.parametrize(
    argnames=('id', 'exp_keywords'),
    argvalues=(
        ('tt0080455', ('action', 'adventure', 'comedy', 'crime', 'music')),  # Blues Brothers
        ('tt6560040', ('crime', 'drama')),                                   # The Forest
        ('tt1572491', ('comedy', 'drama', 'horror')),                        # The Last Circus
        ('tt3286052', ('horror', 'mystery', 'thriller')),                    # February
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_keywords(id, exp_keywords, api, store_response):
    keywords = await api.keywords(id)
    if exp_keywords:
        for kw in exp_keywords:
            assert kw in keywords
    else:
        assert not keywords

@pytest.mark.parametrize(
    argnames=('id', 'exp_summary'),
    argvalues=(
        ('tt0080455', 'Jake Blues, just released from prison'),           # Blues Brothers
        ('tt6560040', 'Sixteen-year-old Jennifer disappears'),            # The Forest
        ('tt1572491', 'young trapeze artist must decide'),                # The Last Circus
        ('tt3286052', 'Two girls must battle a mysterious evil force'),   # February
        ('tt0014838', ''),                                                # The Deadwood Coach
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_summary(id, exp_summary, api, store_response):
    summary = await api.summary(id)
    if exp_summary:
        assert exp_summary in summary
    else:
        assert not summary

@pytest.mark.parametrize(
    argnames=('id', 'exp_title_english', 'exp_title_original'),
    argvalues=(
        ('tt0076759', '', 'Star Wars'),
        ('tt0078243', 'The 36th Chamber of Shaolin', 'Shao Lin san shi liu fang'),
        ('tt0080455', '', 'The Blues Brothers'),
        ('tt0097138', '', 'Cyborg'),
        ('tt0102984', '', 'Stone Cold'),
        ('tt0104684', 'Hard Boiled', 'Lat sau san taam'),
        ('tt0280990', 'The Nest', 'Nid de guêpes'),
        ('tt0348914', '', 'Deadwood'),
        ('tt0396184', '', 'Pusher II'),
        ('tt1127715', '', 'Sin nombre'),
        ('tt1405737', 'Traffic Light', 'Ramzor'),
        ('tt1572491', 'The Last Circus', 'Balada triste de trompeta'),
        ('tt2172934', '', '3 Days to Kill'),
        ('tt2209300', 'Aftermath', 'Poklosie'),
        ('tt2302755', '', 'Olympus Has Fallen'),
        ('tt3286052', "The Blackcoat's Daughter", 'February'),
        ('tt6560040', 'The Forest', 'La forêt'),
        ('tt6616260', 'Deadwind', 'Karppi'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_title_english_original(id, exp_title_english, exp_title_original, api, store_response):
    assert await api.title_english(id) == exp_title_english
    assert await api.title_original(id) == exp_title_original

@pytest.mark.parametrize(
    argnames=('id', 'exp_type'),
    argvalues=(
        ('tt0076759', ReleaseType.movie),
        ('tt0192802', ReleaseType.movie),
        ('tt2372162', ReleaseType.season),
        ('tt1453159', ReleaseType.season),
        ('tt5440238', ReleaseType.episode),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_type(id, exp_type, api, store_response):
    assert await api.type(id) == exp_type

@pytest.mark.parametrize(
    argnames=('id', 'exp_year'),
    argvalues=(
        ('tt0080455', '1980'),  # Blues Brothers
        ('tt1572491', '2010'),  # The Last Circus
        ('tt3286052', '2015'),  # February
        ('tt6560040', '2017'),  # The Forest
        ('tt0348914', '2004'),  # Deadwood
        ('tt6616260', '2018'),  # Karppi
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_year(id, exp_year, api, store_response):
    assert await api.year(id) == exp_year
