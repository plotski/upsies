import asyncio

import pytest

from upsies.tools import dbs


@pytest.mark.asyncio
async def test_info_preserves_affiliation():
    async def foo(id):
        await asyncio.sleep(0.1)
        return f'{id}:foo'

    async def bar(id):
        return f'{id}:bar'

    assert await dbs._common.info('123', foo, bar) == {
        'foo' : '123:foo',
        'bar' : '123:bar',
    }


def test_SearchResult_with_all_info():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'type' : 'movie',
        'year' : '2000',
        'title' : 'Foo',
        'title_original' : 'Le Foo',
        'title_english' : 'Fucking Foo',
        'keywords' : ('foo', 'some bar'),
        'cast' : ('This Guy', 'That Dude'),
        'summary' : 'I dunno.',
        'country' : 'Antarctica',
    }
    sr = dbs._common.SearchResult(**info)
    for k, v in info.items():
        assert getattr(sr, k) == v

def test_SearchResult_with_only_mandatory_info():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'type' : 'movie',
        'year' : '2000',
        'title' : 'Foo',
    }
    sr = dbs._common.SearchResult(**info)
    for k, v in info.items():
        assert getattr(sr, k) == v

def test_SearchResult_with_lacking_mandatory_info():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'type' : 'movie',
        'year' : '2000',
        'title' : 'Foo',
    }
    for k in info:
        info_ = info.copy()
        del info_[k]
        with pytest.raises(TypeError, match=rf'missing 1 required keyword-only argument: {k!r}'):
            dbs._common.SearchResult(**info_)

def test_SearchResult_with_valid_type():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'year' : '2000',
        'title' : 'Foo',
    }
    for type in ('movie', 'series', 'episode', ''):
        sr = dbs._common.SearchResult(type=type, **info)
        assert sr.type == type

def test_SearchResult_with_invalid_type():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'year' : '2000',
        'title' : 'Foo',
    }
    for type in ('foo', 'bar', 'baz', None):
        with pytest.raises(ValueError, match=rf'Invalid type: {type!r}'):
            dbs._common.SearchResult(type=type, **info)


movie_dbs = {dbs.imdb, dbs.tmdb}
series_dbs = {dbs.imdb, dbs.tvmaze, dbs.tmdb}
all_dbs = movie_dbs | series_dbs

@pytest.mark.asyncio
@pytest.mark.parametrize('db', all_dbs, ids=(db.label for db in all_dbs))
async def test_search_returns_SearchResults(db, store_request_cache):
    db.search.cache_clear()
    results = await db.search('Star Wars')
    for r in results:
        assert isinstance(r, dbs._common.SearchResult)

@pytest.mark.asyncio
@pytest.mark.parametrize('db', all_dbs, ids=(db.label for db in all_dbs))
async def test_search_for_specific_year(db, store_request_cache):
    db.search.cache_clear()
    results = await db.search('Star Wars Clone Wars', year=2008)
    assert results[0].year == '2008'
    results = await db.search('Star Wars Clone Wars', year=2003)
    assert results[0].year == '2003'

@pytest.mark.asyncio
@pytest.mark.parametrize('db', movie_dbs, ids=(db.label for db in movie_dbs))
async def test_search_for_movie(db, store_request_cache):
    db.search.cache_clear()
    results = await db.search('Star Wars', type='movie')
    assert results[0].type == 'movie'

@pytest.mark.asyncio
@pytest.mark.parametrize('db', series_dbs, ids=(db.label for db in series_dbs))
async def test_search_for_series(db, store_request_cache):
    db.search.cache_clear()
    results = await db.search('Star Wars', type='series')
    assert results[0].type == 'series'


expected_coroutine_functions = (
    'search', 'info', 'summary', 'title_english', 'title_original', 'year',
)
expected_strings = ('label', '_url_base')

@pytest.mark.asyncio
@pytest.mark.parametrize('db', all_dbs, ids=(db.label for db in all_dbs))
async def test_mandatory_module_attributes(db, store_request_cache):
    for attr in expected_coroutine_functions:
        assert hasattr(db, attr)
        assert asyncio.iscoroutinefunction(getattr(db, attr))

    for attr in expected_strings:
        assert hasattr(db, attr)
        assert isinstance(getattr(db, attr), str)
