from itertools import zip_longest
from unittest.mock import Mock

import pytest

from upsies.utils.types import ReleaseType
from upsies.utils.webdbs import Query, SearchResult, tmdb


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def api():
    return tmdb.TmdbApi()


@pytest.mark.asyncio
async def test_search_handles_id_in_query(api, store_response):
    results = await api.search(Query(id='movie/525'))
    assert len(results) == 1
    assert (await results[0].cast())[:3] == ('Dan Aykroyd', 'John Belushi', 'James Brown')
    assert results[0].countries == ()
    assert await results[0].directors() == ('John Landis',)
    assert results[0].id == 'movie/525'
    assert await results[0].genres() == ('music', 'comedy', 'action', 'crime')
    assert (await results[0].summary()).startswith('Jake Blues, just released from prison')
    assert results[0].title == 'The Blues Brothers'
    assert await results[0].title_english() == 'The Blues Brothers'
    assert await results[0].title_original() == 'The Blues Brothers'
    assert results[0].type == ReleaseType.movie
    assert results[0].url == 'http://themoviedb.org/movie/525'
    assert results[0].year == '1980'

@pytest.mark.asyncio
async def test_search_handles_non_unique_id_in_query(api, store_response):
    results = await api.search(Query(id='525'))
    assert len(results) == 2
    assert results[0].id == 'movie/525'
    assert results[1].id == 'tv/525'


@pytest.mark.asyncio
async def test_search_returns_empty_list_if_title_is_empty(api, store_response):
    assert await api.search(Query('', year='2009')) == []

@pytest.mark.asyncio
async def test_search_returns_list_of_SearchResults(api, store_response):
    results = await api.search(Query('Star Wars'))
    for result in results:
        assert isinstance(result, SearchResult)


@pytest.mark.parametrize(
    argnames=('query', 'exp_top_result'),
    argvalues=(
        (Query('alien', year='1979'), {'title': 'Alien', 'year': '1979'}),
        (Query('aliens', year='1986'), {'title': 'Aliens', 'year': '1986'}),
        (Query('alien', year='1992'), {'title': 'Alien³', 'year': '1992'}),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_for_year(query, exp_top_result, api, store_response):
    results = await api.search(query)
    for k, v in exp_top_result.items():
        assert getattr(results[0], k) == v


@pytest.mark.parametrize(
    argnames=('query', 'exp_titles'),
    argvalues=(
        (Query('wooster', type=ReleaseType.series), ('Jeeves and Wooster', 'The World of Wooster')),
        (Query('wooster', type=ReleaseType.movie), ()),
        (Query('Deadwood', type=ReleaseType.movie), ('Deadwood: The Movie',)),
        (Query('Deadwood', type=ReleaseType.series), ('Deadwood',)),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_for_type(query, exp_titles, api, store_response):
    results = await api.search(query)
    titles = {r.title for r in results}
    if exp_titles:
        for exp_title in exp_titles:
            assert exp_title in titles
    else:
        assert not titles


@pytest.mark.parametrize(
    argnames=('query', 'exp_cast'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), ('Dan Aykroyd', 'John Belushi')),
        (Query('February', year=2017), ('Emma Roberts', 'Kiernan Shipka')),
        (Query('Deadwood', year=2004), ('Timothy Olyphant', 'Ian McShane')),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_cast(query, exp_cast, api, store_response):
    results = await api.search(query)
    cast = await results[0].cast()
    for member in exp_cast:
        assert member in cast


@pytest.mark.asyncio
async def test_search_result_countries(api, store_response):
    results = await api.search(Query('Star Wars'))
    for result in results:
        assert result.countries == ()


@pytest.mark.parametrize(
    argnames=('query', 'exp_id'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), 'movie/525'),
        (Query('February', year=2017), 'movie/334536'),
        (Query('Deadwood', year=2004), 'tv/1406'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_id(query, exp_id, api, store_response):
    results = await api.search(query)
    assert results[0].id == exp_id


@pytest.mark.parametrize(
    argnames=('query', 'exp_directors'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), ('John Landis',)),
        (Query('Deadwood', year=2004), ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_directors(query, exp_directors, api, store_response):
    results = await api.search(query)
    assert await results[0].directors() == exp_directors


@pytest.mark.parametrize(
    argnames=('query', 'exp_genres'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), ('music', 'comedy', 'action', 'crime')),
        (Query('February', year=2017), ('horror', 'thriller')),
        (Query('Deadwood', year=2004), ('crime', 'western')),
        (Query('Farang', year=2017), ('drama',)),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_genres(query, exp_genres, api, store_response):
    results = await api.search(query)
    genres = await results[0].genres()
    if exp_genres:
        for kw in exp_genres:
            assert kw in genres
    else:
        assert not genres


@pytest.mark.parametrize(
    argnames=('query', 'exp_summary'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), 'released from prison'),
        (Query('February', year='2017'), 'spending winter break at their prestigious prep school'),
        (Query('Deadwood', year=2004), 'woven around actual historic events'),
        (Query('Lost & Found Music Studios', year=2015), ''),
        (Query('Anyone Can Play', year=1968), ''),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_summary(query, exp_summary, api, store_response):
    results = await api.search(query)
    summary = await results[0].summary()
    if exp_summary:
        assert exp_summary in summary
    else:
        assert summary == ''


@pytest.mark.parametrize(
    argnames=('query', 'exp_title'),
    argvalues=(
        (Query('Blues Brothers', year=1980), 'The Blues Brothers'),
        (Query('February', year=2017), "The Blackcoat's Daughter"),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_title(query, exp_title, api, store_response):
    results = await api.search(query)
    titles = [r.title for r in results]
    assert exp_title in titles


@pytest.mark.parametrize(
    argnames=('query', 'exp_title_english'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), 'The Blues Brothers'),
        (Query('Deadwood', year=2004), 'Deadwood'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_title_english(query, exp_title_english, api, store_response):
    results = await api.search(query)
    assert await results[0].title_english() == exp_title_english


@pytest.mark.parametrize(
    argnames=('query', 'exp_title_original'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), 'The Blues Brothers'),
        (Query('Deadwind', year=2018), 'Karppi'),
        (Query('Anyone Can Play', year=1968), 'Le dolce signore'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_title_original(query, exp_title_original, api, store_response):
    results = await api.search(query)
    assert await results[0].title_original() == exp_title_original


@pytest.mark.parametrize(
    argnames=('query', 'exp_type'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), ReleaseType.movie),
        (Query('February', year=2017), ReleaseType.movie),
        (Query('Deadwood', year=2004), ReleaseType.series),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_type(query, exp_type, api, store_response):
    results = await api.search(query)
    results_dict = {r.title: r for r in results}
    assert results_dict[query.title].type == exp_type


@pytest.mark.parametrize(
    argnames=('query', 'exp_url'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), 'http://themoviedb.org/movie/525'),
        (Query('February', year=2017), 'http://themoviedb.org/movie/334536'),
        (Query('Deadwood', year=2004), 'http://themoviedb.org/tv/1406'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_url(query, exp_url, api, store_response):
    results = await api.search(query)
    assert results[0].url == exp_url


@pytest.mark.parametrize(
    argnames=('query', 'exp_title', 'exp_year'),
    argvalues=(
        (Query('Blues Brothers', year=1980), 'The Blues Brothers', '1980'),
        (Query('February', year='2017'), "The Blackcoat's Daughter", '2017'),
        (Query('Deadwood', year=2004), 'Deadwood', '2004'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_year(query, exp_title, exp_year, api, store_response):
    results = await api.search(query)
    results_dict = {r.title: r for r in results}
    assert results_dict[exp_title].year == exp_year

@pytest.mark.asyncio
async def test_search_result_parser_failure(api):
    result = tmdb._TmdbSearchResult(tmdb_api=api)
    assert await result.cast() == ()
    assert result.countries == ()
    assert await result.directors() == ()
    assert result.id == ''
    assert await result.genres() == ()
    assert await result.summary() == ''
    assert result.title == ''
    assert await result.title_english() == ''
    assert await result.title_original() == ''
    assert result.type == ReleaseType.unknown
    assert result.url == ''
    assert result.year == ''


@pytest.mark.parametrize(
    argnames=('id', 'exp_cast'),
    argvalues=(
        ('movie/525', (('Dan Aykroyd', 'http://themoviedb.org/person/707-dan-aykroyd'),
                       ('John Belushi', 'http://themoviedb.org/person/7171-john-belushi'))),
        ('movie/334536', (('Emma Roberts', 'http://themoviedb.org/person/34847-emma-roberts'),
                          ('Kiernan Shipka', 'http://themoviedb.org/person/934289-kiernan-shipka'))),
        ('tv/1406', (('Timothy Olyphant', 'http://themoviedb.org/person/18082-timothy-olyphant'),
                     ('Ian McShane', 'http://themoviedb.org/person/6972-ian-mcshane'))),
        ('tv/74802', (('Pihla Viitala', 'http://themoviedb.org/person/93564-pihla-viitala'),
                      ('Lauri Tilkanen', 'http://themoviedb.org/person/124867-lauri-tilkanen'))),
        (None, ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_cast(id, exp_cast, api, store_response):
    cast = (await api.cast(id))[:2]
    if not cast:
        assert exp_cast == ()
    else:
        for person, (name, url) in zip_longest(cast, exp_cast):
            assert person == name
            assert person.url == url


@pytest.mark.parametrize(argnames='id', argvalues=('movie/525', 'movie/334536', 'tv/1406', 'tv/74802'))
@pytest.mark.asyncio
async def test_countries(id, api, store_response):
    with pytest.raises(NotImplementedError, match=r'^Country lookup is not implemented for TMDb$'):
        await api.countries(id)


@pytest.mark.parametrize(
    argnames=('id', 'exp_creators'),
    argvalues=(
        ('movie/125244', ()),
        ('movie/334536', ()),
        ('tv/1406', (('David Milch', 'http://themoviedb.org/person/151295-david-milch'),)),
        ('tv/74802', (('Rike Jokela', 'http://themoviedb.org/person/140497-rike-jokela'),)),
        (None, ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_creators(id, exp_creators, api, store_response):
    creators = await api.creators(id)
    if not creators:
        assert exp_creators == ()
    else:
        for person, (name, url) in zip_longest(creators, exp_creators):
            assert person == name
            assert person.url == url


@pytest.mark.parametrize(
    argnames=('id', 'exp_directors'),
    argvalues=(
        ('movie/125244', (('James Algar', 'http://themoviedb.org/person/5690-james-algar'),
                          ('Jack Kinney', 'http://themoviedb.org/person/74565-jack-kinney'))),
        ('movie/334536', (('Oz Perkins', 'http://themoviedb.org/person/90609-oz-perkins'),)),
        ('tv/1406', ()),
        ('tv/74802', ()),
        (None, ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_directors(id, exp_directors, api, store_response):
    directors = await api.directors(id)
    if not directors:
        assert exp_directors == ()
    else:
        for person, (name, url) in zip_longest(directors, exp_directors):
            assert person == name
            assert person.url == url


@pytest.mark.parametrize(
    argnames=('id', 'exp_genres'),
    argvalues=(
        ('movie/525', ('music', 'comedy', 'action', 'crime')),
        ('movie/334536', ('horror', 'thriller')),
        ('tv/1406', ('crime', 'western')),
        ('tv/74802', ('drama', 'crime')),
        (None, ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_genres(id, exp_genres, api, store_response):
    genres = await api.genres(id)
    if exp_genres:
        for member in exp_genres:
            assert member in genres
    else:
        assert not genres


@pytest.mark.parametrize(
    argnames='id, exp_url',
    argvalues=(
        ('movie/525', 'http://themoviedb.org/t/p/w300_and_h450_bestv2/3DiSrcYELCLkwnjl9EZp2pkKGep.jpg'),
        ('movie/334536', 'http://themoviedb.org/t/p/w300_and_h450_bestv2/b4knSJfiPgWiRzeJFU4nrtyBQDm.jpg'),
        ('tv/1406', 'http://themoviedb.org/t/p/w300_and_h450_bestv2/4Yp35DVbVOAWkfQUIQ7pbh3u0aN.jpg'),
        ('tv/74802', 'http://themoviedb.org/t/p/w300_and_h450_bestv2/cUKqWS2v7D6DVKQze2Iz2netwRH.jpg'),
        ('tv/66260', 'http://themoviedb.org/t/p/w300_and_h450_bestv2/1VaaYENYc8SHsyeudATNZVVfzyx.jpg'),
        ('movie/3405', 'http://themoviedb.org/t/p/w300_and_h450_bestv2/gRGUKC7ESamF1yrV6HdriuKaKxN.jpg'),
        (None, ''),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_poster_url(id, exp_url, api, store_response):
    poster_url = await api.poster_url(id)
    assert poster_url == exp_url


@pytest.mark.parametrize(
    argnames=('id', 'exp_rating'),
    argvalues=(
        ('movie/525', 77.0),
        ('movie/334536', 58.0),
        ('tv/1406', 82.0),
        ('tv/74802', 68.0),
        ('tv/66260', 88.0),
        ('movie/3405', 5.0),
        (None, None),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_rating(id, exp_rating, api, store_response):
    rating = await api.rating(id)
    assert rating == exp_rating


@pytest.mark.parametrize(
    argnames=('id', 'exp_summary'),
    argvalues=(
        ('movie/525', 'released from prison'),
        ('movie/334536', 'spending winter break at their prestigious prep school'),
        ('tv/1406', 'woven around actual historic events'),
        ('tv/74802', 'the body of a young woman on a construction site'),
        ('tv/66260', ''),
        ('movie/3405', ''),
        (None, ''),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_summary(id, exp_summary, api, store_response):
    summary = await api.summary(id)
    assert exp_summary in summary


@pytest.mark.parametrize(
    argnames=('id', 'exp_title_english', 'exp_title_original'),
    argvalues=(
        ('movie/11841', 'The 36th Chamber of Shaolin', '少林三十六房'),
        ('movie/334536', "The Blackcoat's Daughter", "The Blackcoat's Daughter"),
        ('movie/3405', 'Anyone Can Play', 'Le dolce signore'),
        ('movie/525', 'The Blues Brothers', 'The Blues Brothers'),
        ('movie/22156', 'The Nest', 'Nid de guêpes'),
        ('tv/1406', 'Deadwood', 'Deadwood'),
        ('tv/66260', 'Lost & Found Music Studios', 'Lost & Found Music Studios'),
        ('tv/74802', 'Deadwind', 'Karppi'),
        (None, '', ''),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_title_original(id, exp_title_english, exp_title_original, api, store_response):
    title_english = await api.title_english(id)
    assert title_english == exp_title_english
    title_original = await api.title_original(id)
    assert title_original == exp_title_original


@pytest.mark.parametrize(
    argnames=('id', 'exp_type'),
    argvalues=(
        ('movie/525', ReleaseType.movie),
        ('tv/525', ReleaseType.series),
        ('tv/1406', ReleaseType.series),
        ('movie/1406', ReleaseType.movie),
        (None, ReleaseType.unknown),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_type(id, exp_type, api, store_response):
    type = await api.type(id)
    assert type is exp_type


@pytest.mark.parametrize(
    argnames=('id', 'exp_url'),
    argvalues=(
        ('movie/525', f'{tmdb.TmdbApi._url_base}/movie/525'),
        ('/tv/1406', f'{tmdb.TmdbApi._url_base}/tv/1406'),
        (None, ''),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_url(id, exp_url, api):
    assert await api.url(id) == exp_url


@pytest.mark.parametrize(
    argnames=('id', 'exp_year'),
    argvalues=(
        ('movie/525', '1980'),
        ('movie/334536', '2017'),
        ('tv/1406', '2004'),
        ('tv/74802', '2018'),
        (None, ''),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_year(id, exp_year, api, store_response):
    assert await api.year(id) == exp_year
