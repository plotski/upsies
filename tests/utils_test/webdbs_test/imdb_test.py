from itertools import zip_longest
from unittest.mock import Mock

import pytest

from upsies.utils.types import ReleaseType
from upsies.utils.webdbs import Query, SearchResult, imdb


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def api():
    return imdb.ImdbApi()


@pytest.mark.asyncio
async def test_search_handles_id_in_query(api, store_response):
    results = await api.search(Query(id='tt3286052'))
    assert len(results) == 1
    assert (await results[0].cast())[:3] == ('Emma Roberts', 'Kiernan Shipka', 'Lucy Boynton')
    assert await results[0].countries() == ('Canada',)
    assert await results[0].directors() == ('Oz Perkins',)
    assert results[0].id == 'tt3286052'
    assert await results[0].genres() == ('horror', 'mystery', 'thriller')
    assert await results[0].summary() == ('Two girls must battle a mysterious evil force '
                                          'when they get left behind at their boarding school over winter break.')
    assert results[0].title == "The Blackcoat's Daughter"
    assert await results[0].title_english() == "The Blackcoat's Daughter"
    assert await results[0].title_original() == 'February'
    assert results[0].type == ReleaseType.movie
    assert results[0].url == 'https://imdb.com/title/tt3286052'
    assert results[0].year == '2015'


@pytest.mark.asyncio
async def test_search_returns_empty_list_if_title_is_empty(api, store_response):
    assert await api.search(Query('', year='2009')) == []

@pytest.mark.asyncio
async def test_search_returns_list_of_SearchResults(api, store_response):
    results = await api.search(Query('Star Wars'))
    for result in results:
        assert isinstance(result, SearchResult)


@pytest.mark.parametrize(
    argnames=('query', 'exp_title'),
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
async def test_search_for_year(query, exp_title, api, store_response):
    results = await api.search(query)
    if exp_title:
        assert results[0].title == exp_title
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
    argnames=('query', 'exp_countries'),
    argvalues=(
        (Query('Star Wars', type=ReleaseType.movie, year=1977), ('USA', 'UK')),
        (Query('Bron Broen', type=ReleaseType.series, year=2011), ('Sweden', 'Denmark', 'Germany')),
        (Query('The Forest', type=ReleaseType.series, year=2017), ('France',)),
        (Query('Karppi', type=ReleaseType.series, year=2018), ('Finland', 'Germany')),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_country(query, exp_countries, api, store_response):
    results = await api.search(query)
    countries = await results[0].countries()
    assert countries == exp_countries


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
    argnames=('query', 'exp_directors'),
    argvalues=(
        (Query('star wars', type=ReleaseType.movie, year=1977), ('George Lucas',)),
        (Query('balada triste trompeta', type=ReleaseType.movie, year=2010), ('Álex de la Iglesia',)),
        (Query('The Forest', type=ReleaseType.series, year=2017), ()),
        (Query('Karppi', type=ReleaseType.series, year=2018), ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_directors(query, exp_directors, api, store_response):
    results = await api.search(query)
    assert results[0].directors == exp_directors


@pytest.mark.parametrize(
    argnames=('query', 'exp_genres'),
    argvalues=(
        (Query('star wars', type=ReleaseType.movie, year=1977), ('action', 'adventure', 'fantasy')),
        (Query('balada triste trompeta', type=ReleaseType.movie, year=2010), ('action', 'adventure', 'comedy')),
        (Query('The Forest', type=ReleaseType.series, year=2017), ('crime', 'drama')),
        (Query('Deadwood', type=ReleaseType.series, year=2004), ('crime', 'drama', 'history')),
        (Query('The Believer', type=ReleaseType.movie, year=2001), ('drama',)),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_genres(query, exp_genres, api, store_response):
    results = await api.search(query)
    assert results[0].genres == exp_genres


@pytest.mark.parametrize(
    argnames=('query', 'exp_summary'),
    argvalues=(
        (Query('star wars', type=ReleaseType.movie, year=1977),
         ("Luke Skywalker joins forces with a Jedi Knight, a cocky pilot, a Wookiee and two droids to save "
          "the galaxy from the Empire's world-destroying battle station, while also attempting to rescue "
          "Princess Leia from the mysterious Darth Vader.")),
        (Query('balada triste trompeta', type=ReleaseType.movie, year=2010),
         ("A young trapeze artist must decide between her lust for Sergio, the Happy Clown, "
          "or her affection for Javier, the Sad Clown, both of whom are deeply disturbed.")),
        (Query('The Forest', type=ReleaseType.series, year=2017),
         ("Sixteen-year-old Jennifer disappears one night from her village in the Ardennes. "
          "Captain Gaspard Deker leads the investigation with local cop Virginie Musso, "
          "who knew the girl well. They are helped by Eve, a lonely and mysterious woman.")),
        (Query('Deadwood', type=ReleaseType.series, year=2004),
         ("A show set in the late 1800s, revolving around the characters of Deadwood, "
          "South Dakota; a town of deep corruption and crime.")),
        (Query('The Deadwood Coach', type=ReleaseType.movie, year=1924), ''),
        (Query('Two Down', type=ReleaseType.movie, year=2015),
         ("A young woman's world is turned upside down when an injured hit man "
          "takes her hostage at gunpoint in her own home.")),
        (Query('My Best Fiend', type=ReleaseType.movie, year=1999),
         ("In the 1950s, an adolescent Werner Herzog was transfixed by a film performance "
          "of the young Klaus Kinski. Years later, they would share an apartment where, "
          "in an unabated, forty-eight-hour…")),
        (Query('Zero Dark Thirty', type=ReleaseType.movie, year=2012),
         ("A chronicle of the decade-long hunt for al-Qaeda terrorist leader "
          "Osama bin Laden after the September 2001 attacks, and his death "
          "at the hands of the Navy S.E.A.L.s Team 6 in May 2011.")),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_summary(query, exp_summary, api, store_response):
    results = await api.search(query)
    assert results[0].summary == exp_summary


@pytest.mark.parametrize(
    argnames=('query', 'exp_title'),
    argvalues=(
        (Query('Blues Brothers', year=1980), 'The Blues Brothers'),
        (Query('Blues Brothers', year=1998), 'Blues Brothers 2000'),
        (Query('Star Wars', year=2008), 'Star Wars: The Clone Wars'),
        (Query('Star Wars', year=2014), 'Star Wars Rebels'),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_title(query, exp_title, api, store_response):
    results = await api.search(query)
    assert results[0].title == exp_title


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
        (Query('Sin Nombre', type=ReleaseType.movie, year=2009), '', 'Sin Nombre'),
        (Query('Star Wars', type=ReleaseType.movie, year=1977), '', 'Star Wars: Episode IV - A New Hope'),
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
    argnames=('query', 'exp_type'),
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
async def test_search_result_type(query, exp_type, api, store_response):
    results = await api.search(query)
    assert results[0].type == exp_type


@pytest.mark.parametrize(
    argnames=('query', 'exp_url'),
    argvalues=(
        (Query('The Blues Brothers', year=1980), 'https://imdb.com/title/tt0080455'),
        (Query('Deadwood', year=2004), 'https://imdb.com/title/tt0348914'),
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

@pytest.mark.asyncio
async def test_search_result_parser_failure(api):
    result = imdb._ImdbSearchResult(imdb_api=api)
    assert result.cast == ()
    assert await result.countries() == ()
    assert result.directors == ()
    assert result.id == ''
    assert result.genres == ()
    assert result.summary == ''
    assert result.title == ''
    assert await result.title_english() == ''
    assert await result.title_original() == ''
    assert result.type == ReleaseType.series
    assert result.url == ''
    assert result.year == ''


@pytest.mark.parametrize(
    argnames=('id', 'exp_cast'),
    argvalues=(
        # Blues Brothers (movie)
        ('tt0080455', (('John Belushi', 'https://imdb.com/name/nm0000004'),
                       ('Dan Aykroyd', 'https://imdb.com/name/nm0000101'),
                       ('Cab Calloway', 'https://imdb.com/name/nm0130572'))),
        # Wind in the Willows (TV movie)
        ('tt0192802', (('Alan Bennett', 'https://imdb.com/name/nm0003141'),
                       ('Michael Palin', 'https://imdb.com/name/nm0001589'),
                       ('Michael Gambon', 'https://imdb.com/name/nm0002091'))),
        # Bender's Big Score (Video)
        ('tt0471711', (('Billy West', 'https://imdb.com/name/nm0921942'),
                       ('Katey Sagal', 'https://imdb.com/name/nm0005408'),
                       ('John DiMaggio', 'https://imdb.com/name/nm0224007'))),
        # Elephant (TV Short)
        ('tt0097270', (('Gary Walker', 'https://imdb.com/name/nm1281884'),
                       ('Bill Hamilton', 'https://imdb.com/name/nm1685093'),
                       ('Michael Foyle', 'https://imdb.com/name/nm0289432'))),
        # Kung Fury (Short)
        ('tt3472226', (('David Sandberg', 'https://imdb.com/name/nm6247887'),
                       ('Jorma Taccone', 'https://imdb.com/name/nm1672246'),
                       ('Steven Chew', 'https://imdb.com/name/nm7320022'))),
        # The Forest (TV mini-series)
        ('tt6560040', (('Samuel Labarthe', 'https://imdb.com/name/nm0479355'),
                       ('Suzanne Clément', 'https://imdb.com/name/nm0167501'),
                       ('Alexia Barlier', 'https://imdb.com/name/nm1715145'))),
        # Orange Is the New Black (series)
        ('tt2372162', (('Taylor Schilling', 'https://imdb.com/name/nm2279940'),
                       ('Danielle Brooks', 'https://imdb.com/name/nm5335029'),
                       ('Taryn Manning', 'https://imdb.com/name/nm0543383'))),
        # Orange Is the New Black - S07E01 (episode)
        ('tt5440238', (('Taylor Schilling', 'https://imdb.com/name/nm2279940'),
                       ('Natasha Lyonne', 'https://imdb.com/name/nm0005169'),
                       ('Uzo Aduba', 'https://imdb.com/name/nm2499064'))),
        # No cast list
        ('tt0896516', ()),
        (None, ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_cast(id, exp_cast, api, store_response):
    cast = (await api.cast(id))[:3]
    if not cast:
        assert exp_cast == ()
    else:
        for person, (name, url) in zip_longest(cast, exp_cast):
            assert person == name
            assert person.url.rstrip('/') == url.rstrip('/')


@pytest.mark.parametrize(
    argnames=('id', 'exp_countries'),
    argvalues=(
        ('tt0080455', ('USA',)),  # Blues Brothers (movie)
        ('tt3286052', ('Canada',)),  # February (movie)
        ('tt0192802', ('UK',)),  # Wind in the Willows (TV movie)
        ('tt0471711', ('USA',)),  # Bender's Big Score (Video)
        ('tt0097270', ('UK',)),  # Elephant (TV Short)
        ('tt3472226', ('Sweden',)),  # Kung Fury (Short)
        ('tt1733785', ('Sweden', 'Denmark', 'Germany')),  # The Bridge (series)
        ('tt0348914', ('USA',)),  # Deadwood (series)
        ('tt0556307', ('USA',)),  # Deadwood - S02E04 (episode)
        (None, ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_countries(id, exp_countries, api, store_response):
    countries = await api.countries(id)
    assert countries == exp_countries


@pytest.mark.parametrize(
    argnames=('id', 'exp_creators'),
    argvalues=(
        ('tt3286052', ()),  # February (movie)
        ('tt0192802', ()),  # Wind in the Willows (TV movie)
        ('tt0471711', ()),  # Bender's Big Score (Video)
        ('tt0097270', ()),  # Elephant (TV Short)
        ('tt3472226', ()),  # Kung Fury (Short)
        ('tt6560040', (('Delinda Jacobs', 'https://imdb.com/name/nm3064398'),)),  # The Forest (TV mini-series)
        ('tt2372162', (('Jenji Kohan', 'https://imdb.com/name/nm0463176'),)),  # Orange Is the New Black (series)
        ('tt0149460', (('David X. Cohen', 'https://imdb.com/name/nm0169326'),
                       ('Matt Groening', 'https://imdb.com/name/nm0004981'))),  # Futurama
        ('tt5440238', ()),  # Orange Is the New Black - S07E01 (episode)
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
        for person, (name, url) in zip_longest(creators, exp_creators, fillvalue=(None, None)):
            assert person == name
            assert person.url.rstrip('/') == url.rstrip('/')


@pytest.mark.parametrize(
    argnames=('id', 'exp_directors'),
    argvalues=(
        ('tt3286052', (('Oz Perkins', 'https://imdb.com/name/nm0674020'),)),  # February (movie)
        ('tt0192802', (('Dave Unwin', 'https://imdb.com/name/nm0881386'),
                       ('Dennis Abey', 'https://imdb.com/name/nm0008688'))),  # Wind in the Willows (TV movie)
        ('tt0471711', (('Dwayne Carey-Hill', 'https://imdb.com/name/nm1401752'),)),  # Bender's Big Score (Video)
        ('tt0097270', (('Alan Clarke', 'https://imdb.com/name/nm0164639'),)),  # Elephant (TV Short)
        ('tt3472226', (('David Sandberg', 'https://imdb.com/name/nm6247887'),)),  # Kung Fury (Short)
        ('tt6560040', ()),  # The Forest (TV mini-series)
        ('tt2372162', ()),  # Orange Is the New Black (series)
        ('tt5440238', (('Michael Trim', 'https://imdb.com/name/nm0872841'),)),  # Orange Is the New Black - S07E01 (episode)
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
        for person, (name, url) in zip_longest(directors[:3], exp_directors, fillvalue=(None, None)):
            assert person == name
            assert person.url.rstrip('/') == url.rstrip('/')


@pytest.mark.parametrize(
    argnames=('id', 'exp_genres'),
    argvalues=(
        ('tt0080455', ('action', 'adventure', 'comedy')),  # Blues Brothers (movie)
        ('tt0247199', ('drama',)),  # The Believer (single keyword)
        ('tt0192802', ('animation', 'family')),  # Wind in the Willows (TV movie)
        ('tt0471711', ('animation', 'comedy', 'musical')),  # Bender's Big Score (Video)
        ('tt0097270', ('crime', 'drama')),  # Elephant (TV movie)
        ('tt3472226', ('short', 'action', 'comedy')),  # Kung Fury (Short)
        ('tt6560040', ('crime', 'drama')),  # The Forest (mini series)
        ('tt0348914', ('crime', 'drama', 'history')),  # Deadwood (series)
        ('tt0556307', ('crime', 'drama', 'history')),  # Deadwood - S02E04 (episode)
        (None, ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_genres(id, exp_genres, api, store_response):
    genres = await api.genres(id)
    assert genres == exp_genres


@pytest.mark.parametrize(
    argnames='id, exp_poster_url',
    argvalues=(
        ('tt0080455', 'https://m.media-amazon.com/images/M/MV5BYTdlMDExOGUtN2I3MS00MjY5LWE1NTAtYzc3MzIxN2M3OWY1XkEyXkFqcGdeQXVyNzkwMjQ5NzM@._V1_.jpg'),  # Blues Brothers (movie)
        ('tt0192802', 'https://m.media-amazon.com/images/M/MV5BOGQ3NWM5OTAtOThjZS00MzMyLTkwZjMtOWIyOTdlZjFiZGI1XkEyXkFqcGdeQXVyNzMwOTY2NTI@._V1_.jpg'),  # Wind in the Willows (TV movie)
        ('tt0471711', 'https://m.media-amazon.com/images/M/MV5BM2U3NmRiNDItMDQwYy00Y2Q0LWJiYzItNjAzNThkZjFlM2RiXkEyXkFqcGdeQXVyNTA4NzY1MzY@._V1_.jpg'),  # Bender's Big Score (Video)
        ('tt0097270', 'https://m.media-amazon.com/images/M/MV5BMWE0ZTBiOWItY2ZkNS00MzI0LWE5Y2QtYjJmNjM1MGRkZGNmXkEyXkFqcGdeQXVyMzU0MTk1Nzc@._V1_.jpg'),  # Elephant (TV movie)
        ('tt3472226', 'https://m.media-amazon.com/images/M/MV5BMjQwMjU2ODU5NF5BMl5BanBnXkFtZTgwNTU1NjM4NTE@._V1_.jpg'),  # Kung Fury (Short)
        ('tt6560040', 'https://m.media-amazon.com/images/M/MV5BMzY5NThkOWItN2I1OC00MzQ2LThlYjktMGExYTk2YzM1ZGRmXkEyXkFqcGdeQXVyODEyMzI2OTE@._V1_.jpg'),  # The Forest (mini series)
        ('tt0348914', 'https://m.media-amazon.com/images/M/MV5BNDJhMjUzMDYtNzc4MS00Nzk2LTkyMGQtN2M5NTczYTZmYmY5XkEyXkFqcGdeQXVyMzU3MTc5OTE@._V1_.jpg'),  # Deadwood (series)
        ('tt0556307', ''),  # Deadwood - S02E04 (episode)
        (None, ''),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_poster_url(id, exp_poster_url, api, store_response):
    poster_url = await api.poster_url(id)
    assert poster_url == exp_poster_url


@pytest.mark.parametrize(
    argnames=('id', 'exp_rating'),
    argvalues=(
        ('tt0080455', 7.9),  # Blues Brothers (movie)
        ('tt0192802', 7.6),  # Wind in the Willows (TV movie)
        ('tt0471711', 7.6),  # Bender's Big Score (Video)
        ('tt0097270', 7.2),  # Elephant (TV movie)
        ('tt3472226', 8.0),  # Kung Fury (Short)
        ('tt6560040', 7.2),  # The Forest (mini series)
        ('tt0348914', 8.6),  # Deadwood (series)
        ('tt0556307', 8.3),  # Deadwood - S02E04 (episode)
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
        ('tt0080455', ('Jake Blues, just released from prison, puts together '
                       'his old band to save the Catholic home where he and '
                       'his brother Elwood were raised.')),  # Blues Brothers (movie)
        ('tt0192802', ('When three close friends Mole, Ratty and Badger '
                       'find out that the infamous Mr. Toad of Toad Hall '
                       'has been up to no good, they must find him and change '
                       'his ways for good.')),  # Wind in the Willows (TV movie)
        ('tt0471711', ('Planet Express sees a hostile takeover and Bender falls into the hands of '
                       'criminals where he is used to fulfill their schemes.')),  # Bender's Big Score (Video)
        ('tt0097270', ('A depiction of a series of violent killings in Northern Ireland '
                       'with no clue as to exactly who is responsible.')),  # Elephant (TV Short)
        ('tt3472226', ('In 1985, Kung Fury, the toughest martial artist cop in Miami, '
                       'goes back in time to kill the worst criminal of all time '
                       '- Kung Führer, a.k.a. Adolf Hitler.')),  # Kung Fury (Short)
        ('tt6560040', ('Sixteen-year-old Jennifer disappears one night from her village '
                       'in the Ardennes. Captain Gaspard Deker leads the investigation with '
                       'local cop Virginie Musso, who knew the girl well. They are helped '
                       'by Eve, a lonely and mysterious woman.')),  # The Forest (TV mini-series)
        ('tt0348914', ('A show set in the late 1800s, revolving around '
                       'the characters of Deadwood, South Dakota; a town '
                       'of deep corruption and crime.')),  # Deadwood (series)
        ('tt0556307', ('Doc contemplates a procedure that could cure Swearengen - or kill him. '
                       'Bullock attempts to settle into domesticity, while Sol gets a new '
                       "student bookkeeper - Trixie. Alma cuts ties with Sofia's tutor, "
                       'Miss Isringhausen. Joanie and Maddie argue over the business. The '
                       "County Commissioner's arrival spawns rumors about the camp's future "
                       'and legal ownership of the gold claims.')),  # Deadwood - S02E04 (episode)
        ('tt0014838', ''),  # The Deadwood Coach
        # Links in summary
        ('tt0200849', ('In the 1950s, an adolescent Werner Herzog was transfixed by a '
                       'film performance of the young Klaus Kinski. Years later, they would share '
                       'an apartment where, in an unabated, forty-eight-hour fit of rage, Kinski '
                       'completely destroyed the bathroom. From this chaos, a violent, love-hate, '
                       'profoundly creative partnership was born. In 1972, Herzog cast Kinski in '
                       'Aguirre, der Zorn Gottes (1972). Four more films would follow. In this '
                       'personal documentary, Herzog traces the often violent ups and downs of '
                       'their relationship, revisiting the various locations of their films and '
                       'talking to the people they worked with.')),  # Mein liebster Feind
        (None, ''),
    ),
    ids=lambda value: str(value)[:30] or '<empty>',
)
@pytest.mark.asyncio
async def test_summary(id, exp_summary, api, store_response):
    summary = await api.summary(id)
    assert summary == exp_summary


@pytest.mark.parametrize(
    argnames=('id', 'exp_title_english', 'exp_title_original'),
    argvalues=(
        ('tt0076759', '', 'Star Wars: Episode IV - A New Hope'),
        ('tt0078243', 'The 36th Chamber of Shaolin', 'Shao Lin san shi liu fang'),
        ('tt0080455', '', 'The Blues Brothers'),
        ('tt0097138', '', 'Cyborg'),
        ('tt0102984', '', 'Stone Cold'),
        ('tt0104684', 'Hard Boiled', 'Lat sau san taam'),
        ('tt0280990', 'The Nest', 'Nid de guêpes'),
        ('tt0348914', '', 'Deadwood'),
        ('tt0396184', '', 'Pusher II'),
        ('tt1127715', '', 'Sin Nombre'),
        ('tt1405737', 'Traffic Light', 'Ramzor'),
        ('tt1413492', '', '12 Strong'),
        ('tt1572491', 'The Last Circus', 'Balada triste de trompeta'),
        ('tt1866210', '', 'Wrecked'),  # No AKAs available
        ('tt2172934', '', '3 Days to Kill'),
        ('tt2209300', 'Aftermath', 'Poklosie'),
        ('tt2302755', '', 'Olympus Has Fallen'),
        ('tt3286052', "The Blackcoat's Daughter", 'February'),
        ('tt6560040', 'The Forest', 'La forêt'),
        ('tt6616260', 'Deadwind', 'Karppi'),
        ('tt7534328', 'These Woods Are Haunted', 'Terror in the Woods'),
        (None, '', ''),
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
        ('tt3286052', ReleaseType.movie),    # February AKA The Blackcoat's Daughter
        ('tt0080455', ReleaseType.movie),    # Blues Brothers (movie)
        ('tt0080455', ReleaseType.movie),    # Blues Brothers (movie)
        ('tt0192802', ReleaseType.movie),    # Wind in the Willows (TV movie)
        ('tt0471711', ReleaseType.movie),    # Bender's Big Score (Video)
        ('tt0097270', ReleaseType.movie),    # Elephant (TV movie)
        ('tt3472226', ReleaseType.movie),    # Kung Fury (Short)
        ('tt0463986', ReleaseType.movie),    # The Feast (short)
        ('tt6560040', ReleaseType.season),   # The Forest (mini series)
        ('tt0348914', ReleaseType.season),   # Deadwood (series)
        ('tt0556307', ReleaseType.episode),  # Deadwood - S02E04 (episode)
        (None, ReleaseType.unknown),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_type(id, exp_type, api, store_response):
    assert await api.type(id) == exp_type


@pytest.mark.asyncio
async def test_url(api):
    assert await api.url('foo') == api._url_base + '/title/foo'
    assert await api.url(None) == ''


@pytest.mark.parametrize(
    argnames=('id', 'exp_year'),
    argvalues=(
        ('tt0080455', '1980'),  # Blues Brothers (movie)
        ('tt0192802', '1995'),  # Wind in the Willows (TV movie)
        ('tt0471711', '2007'),  # Bender's Big Score (Video)
        ('tt0097270', '1989'),  # Elephant (TV Short)
        ('tt3472226', '2015'),  # Kung Fury (Short)
        ('tt6560040', '2017'),  # The Forest (mini series)
        ('tt0348914', '2004'),  # Deadwood (series)
        ('tt0556307', '2005'),  # Deadwood - S02E04 (episode)
        ('tt0048918', '1956'),  # 1984 (movie)
        (None, ''),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_year(id, exp_year, api, store_response):
    assert await api.year(id) == exp_year
