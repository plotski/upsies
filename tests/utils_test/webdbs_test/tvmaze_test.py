from itertools import zip_longest
from unittest.mock import AsyncMock, call

import pytest

from upsies.utils.types import ReleaseType
from upsies.utils.webdbs import Query, SearchResult, tvmaze


@pytest.fixture
def api():
    return tvmaze.TvmazeApi()


def test_sanitize_query(api):
    q = Query('The Foo', type='movie', year='2000')
    assert api.sanitize_query(q) == Query('The Foo', type='unknown', year='2000')
    with pytest.raises(TypeError, match=r'^Not a Query instance: 123$'):
        api.sanitize_query(123)


@pytest.mark.asyncio
async def test_search_handles_id_in_query(api, store_response):
    results = await api.search(Query(id=35256))
    assert len(results) == 1
    assert (await results[0].cast())[:3] == ('Son Ye Jin', 'Jung Hae In', 'Jang So Yun')
    assert results[0].countries == ('South Korea',)
    assert results[0].id == 35256
    assert results[0].genres == ('drama', 'romance')
    assert results[0].summary.startswith('Yoon Jin Ah is a single woman in her 30s who works')
    assert results[0].title == 'Something in the Rain'
    assert await results[0].title_english() == 'Something in the Rain'
    assert await results[0].title_original() == 'Bap Jal Sajuneun Yeppeun Nuna'
    assert results[0].type == ReleaseType.season
    assert results[0].url == 'https://www.tvmaze.com/shows/35256/something-in-the-rain'
    assert results[0].year == '2018'

@pytest.mark.asyncio
async def test_search_returns_empty_list_if_title_is_empty(api, store_response):
    assert await api.search(Query('', year='2009')) == []

@pytest.mark.asyncio
async def test_search_returns_list_of_SearchResults(api, store_response):
    results = await api.search(Query('Star Wars'))
    for result in results:
        assert isinstance(result, SearchResult)


@pytest.mark.parametrize(
    argnames=('query', 'exp_titles'),
    argvalues=(
        (Query('Star Wars', year=2003), ('Star Wars: Clone Wars',)),
        (Query('Star Wars', year='2003'), ('Star Wars: Clone Wars',)),
        (Query('Star Wars', year=2014), ('Star Wars: Rebels',)),
        (Query('Star Wars', year='1990'), ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_for_year(query, exp_titles, api, store_response):
    results = await api.search(query)
    titles = {r.title for r in results}
    assert titles == set(exp_titles)


@pytest.mark.parametrize(
    argnames=('query', 'exp_titles'),
    argvalues=(
        (Query('star wars clone', type=ReleaseType.series), ('Star Wars: Clone Wars', 'Star Wars: The Clone Wars')),
        (Query('yes minister', type=ReleaseType.series), ('Yes Minister', 'Yes, Prime Minister', 'Yes, Prime Minister')),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_for_series(query, exp_titles, api, store_response):
    results = await api.search(query)
    titles = {r.title for r in results}
    assert titles == set(exp_titles)


@pytest.mark.parametrize(
    argnames=('query', 'exp_titles'),
    argvalues=(
        (Query('star wars', type=ReleaseType.movie), ()),
        (Query('yes minister', type=ReleaseType.movie), ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_for_movie(query, exp_titles, api, store_response):
    assert await api.search(query) == []


@pytest.mark.parametrize(
    argnames=('title', 'exp_cast'),
    argvalues=(
        ('Star Wars: Clone Wars', ('André Sogliuzzo', 'John DiMaggio')),
        ('Star Wars: Rebels', ('Taylor Gray', 'Vanessa Marshall')),
        ('Star Wars Resistance', ('Christopher Sean', 'Suzie McGrath')),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_search_result_cast(title, exp_cast, api, store_response):
    results = await api.search(Query('Star Wars'))
    results_dict = {r.title: r for r in results}
    cast = await results_dict[title].cast()
    for member in exp_cast:
        assert member in cast


@pytest.mark.parametrize(
    argnames=('title', 'exp_countries'),
    argvalues=(
        ('Star Wars: Clone Wars', ('United States',)),
        ('Something in the Rain', ('South Korea',)),
        ('Le Chalet', ('France',)),
        ('Bron / Broen', ('Sweden',)),
    ),
)
@pytest.mark.asyncio
async def test_search_result_countries(title, exp_countries, api, store_response):
    results = await api.search(Query(title))
    results_dict = {r.title: r for r in results}
    assert results_dict[title].countries == exp_countries


@pytest.mark.parametrize(
    argnames=('title', 'exp_id'),
    argvalues=(
        ('Star Wars: Clone Wars', 1259),
        ('Star Wars: Rebels', 117),
        ('Star Wars Resistance', 36483),
    ),
)
@pytest.mark.asyncio
async def test_search_result_id(title, exp_id, api, store_response):
    results = await api.search(Query('Star Wars'))
    results_dict = {r.title: r for r in results}
    assert results_dict[title].id == exp_id


@pytest.mark.asyncio
async def test_search_result_directors(api, store_response):
    results = await api.search(Query('Star Wars'))
    for result in results:
        assert result.directors == ()


@pytest.mark.parametrize(
    argnames=('title', 'exp_genres'),
    argvalues=(
        ('Star Wars: Clone Wars', ('action', 'science-fiction')),
        ('Something in the Rain', ('drama', 'romance')),
        ('Le Chalet', ('thriller', 'mystery')),
    ),
)
@pytest.mark.asyncio
async def test_search_result_genres(title, exp_genres, api, store_response):
    results = await api.search(Query(title))
    results_dict = {r.title: r for r in results}
    for kw in exp_genres:
        assert kw in results_dict[title].genres


@pytest.mark.parametrize(
    argnames=('title', 'summary'),
    argvalues=(
        ('Star Wars: Clone Wars', 'downfall of the Jedi'),
        ('Star Wars: Rebels', 'set five years before the events of Star Wars: Episode IV'),
        ('Star Wars Resistance', 'Kazuda Xiono'),
    ),
)
@pytest.mark.asyncio
async def test_search_result_summary(title, summary, api, store_response):
    results = await api.search(Query('Star Wars'))
    results_dict = {r.title: r for r in results}
    assert summary in results_dict[title].summary


@pytest.mark.asyncio
async def test_search_result_title_english(api, store_response, mocker):
    mock_title_english = mocker.patch.object(
        api, 'title_english', AsyncMock(return_value='The English Title')
    )
    results = await api.search(Query('Star Wars'))
    for result in results:
        assert await result.title_english() == 'The English Title'
    assert sorted(mock_title_english.call_args_list) == [
        call(result.id) for result in sorted(results, key=lambda r: r.id)
    ]


@pytest.mark.asyncio
async def test_search_result_title_original(api, store_response, mocker):
    mock_title_original = mocker.patch.object(
        api, 'title_original', AsyncMock(return_value='The Original Title')
    )
    results = await api.search(Query('Star Wars'))
    for result in results:
        assert await result.title_original() == 'The Original Title'
    assert sorted(mock_title_original.call_args_list) == [
        call(result.id) for result in sorted(results, key=lambda r: r.id)
    ]


@pytest.mark.parametrize(
    argnames=('id', 'exp_title'),
    argvalues=(
        (1259, 'Star Wars: Clone Wars'),
        (117, 'Star Wars: Rebels'),
        (36483, 'Star Wars Resistance'),
    ),
)
@pytest.mark.asyncio
async def test_search_result_title(id, exp_title, api, store_response):
    results = await api.search(Query('Star Wars'))
    results_dict = {r.id: r for r in results}
    assert results_dict[id].title == exp_title


@pytest.mark.asyncio
async def test_search_result_type(api, store_response):
    results = await api.search(Query('Star Wars'))
    for result in results:
        assert result.type is ReleaseType.series


@pytest.mark.parametrize(
    argnames=('title', 'exp_url'),
    argvalues=(
        ('Star Wars: Clone Wars', 'https://www.tvmaze.com/shows/1259/star-wars-clone-wars'),
        ('Star Wars: Rebels', 'https://www.tvmaze.com/shows/117/star-wars-rebels'),
        ('Star Wars Resistance', 'https://www.tvmaze.com/shows/36483/star-wars-resistance'),
    ),
)
@pytest.mark.asyncio
async def test_search_result_url(title, exp_url, api, store_response):
    results = await api.search(Query('Star Wars'))
    results_dict = {r.title: r for r in results}
    assert results_dict[title].url == exp_url


@pytest.mark.parametrize(
    argnames=('title', 'exp_year'),
    argvalues=(
        ('Star Wars: Clone Wars', '2003'),
        ('Star Wars: Rebels', '2014'),
        ('Star Wars Resistance', '2018'),
    ),
)
@pytest.mark.asyncio
async def test_search_result_year(title, exp_year, api, store_response):
    results = await api.search(Query('Star Wars'))
    results_dict = {r.title: r for r in results}
    assert results_dict[title].year == exp_year


@pytest.mark.parametrize(
    argnames=('id', 'exp_cast'),
    argvalues=(
        (1259, (('André Sogliuzzo', 'https://www.tvmaze.com/people/53172/andre-sogliuzzo'),
                ('Anthony Daniels', 'https://www.tvmaze.com/people/49258/anthony-daniels'))),
        (117, (('Taylor Gray', 'https://www.tvmaze.com/people/25382/taylor-gray'),
               ('Vanessa Marshall', 'https://www.tvmaze.com/people/25383/vanessa-marshall'))),
        (36483, (('Christopher Sean', 'https://www.tvmaze.com/people/5900/christopher-sean'),
                 ('Scott Lawrence', 'https://www.tvmaze.com/people/9486/scott-lawrence'))),
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

@pytest.mark.asyncio
async def test_cast_deduplicates_actors_with_multiple_roles(api, store_response):
    cast = await api.cast(83)  # The Simpsons
    assert cast.count('Dan Castellaneta') == 1
    assert cast.count('Julie Kavner') == 1
    assert cast.count('Yeardley Smith') == 1
    assert cast.count('Nancy Cartwright') == 1
    assert cast.count('Harry Shearer') == 1


@pytest.mark.parametrize(
    argnames=('id', 'exp_countries'),
    argvalues=(
        (1259, ('United States',)),
        (35256, ('South Korea',)),
        (36072, ('France',)),
        (1910, ('Sweden',)),
        (None, ()),
    ),
)
@pytest.mark.asyncio
async def test_countries(id, exp_countries, api, store_response):
    assert await api.countries(id) == exp_countries


@pytest.mark.parametrize(
    argnames=('id', 'exp_creators'),
    argvalues=(
        (170, (('Jenji Kohan', 'https://www.tvmaze.com/people/29524/jenji-kohan'),)),
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
        (1259, ()),
        (117, ()),
        (36483, ()),
        (None, ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_directors(id, exp_directors, api, store_response):
    directors = await api.directors(id)
    assert directors == exp_directors


@pytest.mark.parametrize(
    argnames=('id', 'exp_genres'),
    argvalues=(
        (1259, ('action', 'science-fiction')),
        (35256, ('drama', 'romance')),
        (36072, ('thriller', 'mystery')),
        (None, ()),
    ),
)
@pytest.mark.asyncio
async def test_genres(id, exp_genres, api, store_response):
    genres = await api.genres(id)
    for kw in exp_genres:
        assert kw in genres


@pytest.mark.parametrize(
    argnames='id, season, exp_url',
    argvalues=(
        (1259, None, 'https://static.tvmaze.com/uploads/images/medium_portrait/393/983792.jpg'),
        (35256, None, 'https://static.tvmaze.com/uploads/images/medium_portrait/149/374799.jpg'),
        (36072, None, 'https://static.tvmaze.com/uploads/images/medium_portrait/201/504665.jpg'),
        (1259, 3, 'https://static.tvmaze.com/uploads/images/medium_portrait/393/983792.jpg'),
        (1910, 2, 'https://static.tvmaze.com/uploads/images/medium_portrait/252/631184.jpg'),
        (117, 1, 'https://static.tvmaze.com/uploads/images/medium_portrait/393/983692.jpg'),
        (None, None, ''),
    ),
)
@pytest.mark.asyncio
async def test_poster_url(id, season, exp_url, api, store_response):
    poster_url = await api.poster_url(id, season=season)
    assert poster_url == exp_url


@pytest.mark.parametrize(
    argnames=('id', 'exp_rating'),
    argvalues=(
        (1259, 8.1),
        (35256, 7.9),
        (36072, 7.6),
        (None, None),
    ),
)
@pytest.mark.asyncio
async def test_rating(id, exp_rating, api, store_response):
    rating = await api.rating(id)
    assert rating == exp_rating


@pytest.mark.parametrize(
    argnames=('id', 'exp_runtimes'),
    argvalues=(
        (1259, {'default': 15}),
        (35256, {'default': 60}),
        (36072, {'default': 50}),
        (None, {}),
    ),
)
@pytest.mark.asyncio
async def test_runtimes(id, exp_runtimes, api, store_response):
    runtimes = await api.runtimes(id)
    assert runtimes == exp_runtimes


@pytest.mark.parametrize(
    argnames=('id', 'exp_summary'),
    argvalues=(
        (1259, ('The Clone Wars television series chronicles the events taking place '
                'between Star Wars Episode II: Attack of the Clones and '
                'Star Wars Episode III: Revenge of the Sith. The Clone Wars will ultimately lead '
                'to the downfall of the Jedi and the rise of the Galactic Empire.')),
        (35256, ('Yoon Jin Ah is a single woman in her 30s who works as a store supervisor '
                 'in a coffee shop. Despite being an easygoing person, she lives a rather empty '
                 "life. She suddenly feels romantic feelings towards her best friend's younger "
                 'brother, Seo Joon Hee, a designer at a video game company, '
                 'who has just returned from working abroad.')),
        (36072, ('Friends gathered at a remote chalet in the French Alps for a summer getaway '
                 'are caught in a deadly trap as a dark secret from the past comes to light.')),
        (None, ''),
    ),
)
@pytest.mark.asyncio
async def test_summary(id, exp_summary, api, store_response):
    assert await api.summary(id) == exp_summary


@pytest.mark.parametrize(
    argnames=('id', 'exp_title_english'),
    argvalues=(
        (35256, 'Something in the Rain'),
        (37993, 'Traffic Light'),
        (36072, 'The Chalet'),
        (None, ''),
    ),
)
@pytest.mark.asyncio
async def test_title_english(id, exp_title_english, api, store_response):
    assert await api.title_english(id) == exp_title_english


@pytest.mark.parametrize(
    argnames=('id', 'exp_title_original'),
    argvalues=(
        (35256, 'Bap Jal Sajuneun Yeppeun Nuna'),
        (37993, 'Ramzor'),
        (36072, 'Le chalet'),
        (None, ''),
    ),
)
@pytest.mark.asyncio
async def test_title_original(id, exp_title_original, api, store_response):
    assert await api.title_original(id) == exp_title_original


@pytest.mark.parametrize('id', (1259, 35256, 36072, None))
@pytest.mark.asyncio
async def test_type(id, api, store_response):
    await api.type(id) == ReleaseType.unknown


@pytest.mark.parametrize(
    argnames=('id', 'exp_url'),
    argvalues=(
        (1259, 'https://www.tvmaze.com/shows/1259/star-wars-clone-wars'),
        (35256, 'https://www.tvmaze.com/shows/35256/something-in-the-rain'),
        (36072, 'https://www.tvmaze.com/shows/36072/le-chalet'),
        (None, ''),
    ),
)
@pytest.mark.asyncio
async def test_url(id, exp_url, api, store_response):
    assert await api.url(id) == exp_url


@pytest.mark.parametrize(
    argnames=('id', 'exp_year'),
    argvalues=(
        (1259, '2003'),
        (35256, '2018'),
        (36072, '2018'),
        (None, ''),
    ),
)
@pytest.mark.asyncio
async def test_year(id, exp_year, api, store_response):
    assert await api.year(id) == exp_year


@pytest.mark.parametrize(
    argnames=('id', 'exp_imdb_id'),
    argvalues=(
        (35256, 'tt8078816'),
        (37993, 'tt1405737'),
        (36072, 'tt8168678'),
        (None, ''),
    ),
)
@pytest.mark.asyncio
async def test_imdb_id(id, exp_imdb_id, api, store_response):
    assert await api.imdb_id(id) == exp_imdb_id


@pytest.mark.parametrize(
    argnames=('id', 'season', 'episode', 'exp_episode'),
    argvalues=(
        (35256, 1, 5, {
            'date': '2018-04-13',
            'episode': '5',
            'season': '1',
            'summary': ("Setting aside her guilt, Jin Ah spends the night at Jun Hee's place. "
                        "Back at work after the business trip, she gets called to Director Nam's office."),
            'title': 'Episode 5',
            'url': 'https://www.tvmaze.com/episodes/1436940/something-in-the-rain-1x05-episode-5',
        }),
        (37993, 3, 10, {
            'date': '2011-08-13',
            'episode': '10',
            'season': '3',
            'summary': '',
            'title': 'Test in Shlomy',
            'url': 'https://www.tvmaze.com/episodes/1505367/ramzor-3x10-test-in-shlomy',
        }),
        (117, 1, 3, {
            'date': '2014-10-27',
            'episode': '3',
            'season': '1',
            'summary': 'The Rebels undergo a daring rescue mission, only to find themselves facing a powerful foe.',
            'title': 'Rise of the Old Masters',
            'url': 'https://www.tvmaze.com/episodes/9023/star-wars-rebels-1x03-rise-of-the-old-masters',
        }),
        (None, 1, 3, {
            'date': '',
            'episode': '',
            'season': '',
            'summary': '',
            'title': '',
            'url': '',
        }),
    ),
)
@pytest.mark.asyncio
async def test_episode(id, season, episode, exp_episode, api, store_response):
    assert await api.episode(id, season, episode) == exp_episode


@pytest.mark.parametrize(
    argnames=('id', 'exp_status'),
    argvalues=(
        (35256, 'Ended'),
        (37993, 'Ended'),
        (36072, 'Ended'),
        (None, ''),
    ),
)
@pytest.mark.asyncio
async def test_status(id, exp_status, api, store_response):
    assert await api.status(id) == exp_status
