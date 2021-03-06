from unittest.mock import Mock, call

import pytest

from upsies.utils.types import ReleaseType
from upsies.utils.webdbs import Query, SearchResult, tvmaze


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def api():
    return tvmaze.TvmazeApi()


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
        (Query('Star Wars', year='2008'), ('Star Wars: The Clone Wars',)),
        (Query('Star Wars', year=2014), ('Star Wars Rebels',)),
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
        ('Star Wars Rebels', ('Taylor Gray', 'Vanessa Marshall')),
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
        ('Star Wars: Clone Wars', ['United States']),
        ('Something in the Rain', ['Korea, Republic of']),
        ('Le Chalet', ['France']),
        ('Bron / Broen', ['Sweden']),
    ),
)
@pytest.mark.asyncio
async def test_search_result_countries(title, exp_countries, api, store_response):
    results = await api.search(Query(title))
    results_dict = {r.title: r for r in results}
    print(results_dict)
    assert results_dict[title].countries == exp_countries


@pytest.mark.parametrize(
    argnames=('title', 'exp_id'),
    argvalues=(
        ('Star Wars: Clone Wars', 1259),
        ('Star Wars Rebels', 117),
        ('Star Wars Resistance', 36483),
    ),
)
@pytest.mark.asyncio
async def test_search_result_id(title, exp_id, api, store_response):
    results = await api.search(Query('Star Wars'))
    results_dict = {r.title: r for r in results}
    assert results_dict[title].id == exp_id


@pytest.mark.asyncio
async def test_search_result_director(api, store_response):
    results = await api.search(Query('Star Wars'))
    for result in results:
        assert result.director == ''


@pytest.mark.parametrize(
    argnames=('title', 'exp_keywords'),
    argvalues=(
        ('Star Wars: Clone Wars', ('action', 'science-fiction')),
        ('Something in the Rain', ('drama', 'romance')),
        ('Le Chalet', ('thriller', 'mystery')),
    ),
)
@pytest.mark.asyncio
async def test_search_result_keywords(title, exp_keywords, api, store_response):
    results = await api.search(Query(title))
    results_dict = {r.title: r for r in results}
    for kw in exp_keywords:
        assert kw in results_dict[title].keywords


@pytest.mark.parametrize(
    argnames=('title', 'summary'),
    argvalues=(
        ('Star Wars: Clone Wars', 'downfall of the Jedi'),
        ('Star Wars Rebels', 'set five years before the events of Star Wars: Episode IV'),
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
        (117, 'Star Wars Rebels'),
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
        ('Star Wars Rebels', 'https://www.tvmaze.com/shows/117/star-wars-rebels'),
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
        ('Star Wars Rebels', '2014'),
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
        (1259, ('André Sogliuzzo', 'John DiMaggio')),
        (117, ('Taylor Gray', 'Vanessa Marshall')),
        (36483, ('Christopher Sean', 'Suzie McGrath')),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_cast(id, exp_cast, api, store_response):
    cast = await api.cast(id)
    for member in exp_cast:
        assert member in cast


@pytest.mark.parametrize(
    argnames=('id', 'exp_directors'),
    argvalues=(
        (1259, ()),
        (117, ()),
        (36483, ()),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_directors(id, exp_directors, api, store_response):
    directors = await api.directors(id)
    assert directors == exp_directors


@pytest.mark.parametrize(
    argnames=('id', 'exp_creators'),
    argvalues=(
        (170, ('Jenji Kohan',)),
    ),
    ids=lambda value: str(value),
)
@pytest.mark.asyncio
async def test_creators(id, exp_creators, api, store_response):
    creators = await api.creators(id)
    assert creators == exp_creators


@pytest.mark.parametrize(
    argnames=('id', 'exp_countries'),
    argvalues=(
        (1259, ['United States']),
        (35256, ['Korea, Republic of']),
        (36072, ['France']),
        (1910, ['Sweden']),
    ),
)
@pytest.mark.asyncio
async def test_countries(id, exp_countries, api, store_response):
    assert await api.countries(id) == exp_countries


@pytest.mark.parametrize(
    argnames=('id', 'exp_keywords'),
    argvalues=(
        (1259, ('action', 'science-fiction')),
        (35256, ('drama', 'romance')),
        (36072, ('thriller', 'mystery')),
    ),
)
@pytest.mark.asyncio
async def test_keywords(id, exp_keywords, api, store_response):
    keywords = await api.keywords(id)
    for kw in exp_keywords:
        assert kw in keywords


@pytest.mark.parametrize(
    argnames=('id', 'exp_summary'),
    argvalues=(
        (1259, 'downfall of the Jedi'),
        (35256, 'coffee shop'),
        (36072, 'dark secret from the past'),
    ),
)
@pytest.mark.asyncio
async def test_summary(id, exp_summary, api, store_response):
    assert exp_summary in await api.summary(id)


@pytest.mark.parametrize(
    argnames=('id', 'exp_title_english'),
    argvalues=(
        (35256, 'Something in the Rain'),
        (37993, 'Traffic Light'),
        (36072, 'The Chalet'),
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
    ),
)
@pytest.mark.asyncio
async def test_title_original(id, exp_title_original, api, store_response):
    assert await api.title_original(id) == exp_title_original


@pytest.mark.parametrize('id', (1259, 35256, 36072))
@pytest.mark.asyncio
async def test_type(id, api, store_response):
    with pytest.raises(NotImplementedError, match=r'^Type lookup is not implemented for TVmaze$'):
        await api.type(id)


@pytest.mark.asyncio
async def test_url(api):
    assert await api.url('123') == api._url_base + '/shows/123'


@pytest.mark.parametrize(
    argnames=('id', 'exp_year'),
    argvalues=(
        (1259, '2003'),
        (35256, '2018'),
        (36072, '2018'),
    ),
)
@pytest.mark.asyncio
async def test_year(id, exp_year, api, store_response):
    assert await api.year(id) == exp_year
