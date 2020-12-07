import asyncio

import pytest

from upsies.tools import webdbs
from upsies.tools.webdbs.common import Type


def test_Query_title():
    with pytest.raises(TypeError):
        webdbs.Query()
    assert webdbs.Query('The Title').title == 'The Title'

def test_Query_year():
    assert webdbs.Query('The Title', year='2000').year == '2000'
    assert webdbs.Query('The Title', year=2000).year == '2000'
    with pytest.raises(ValueError, match=r'^Invalid year: 1000$'):
        webdbs.Query('The Title', year=1000)
    with pytest.raises(ValueError, match=r'^Invalid year: 3000$'):
        webdbs.Query('The Title', year='3000')
    with pytest.raises(ValueError, match=r'invalid literal for int\(\)'):
        webdbs.Query('The Title', year=2000.5)

@pytest.mark.parametrize('typ', list(Type))
def test_Query_valid_type(typ):
    assert webdbs.Query('The Title', type=typ).type is typ

def test_Query_invalid_type():
    with pytest.raises(ValueError, match=r"^Invalid type: 'foo'$"):
        webdbs.Query('The Title', type='foo')

@pytest.mark.parametrize(
    argnames=('a', 'b'),
    argvalues=(
        (webdbs.Query('The Title'), webdbs.Query('The Title')),
        (webdbs.Query('The Title'), webdbs.Query('the title')),
        (webdbs.Query('The Title'), webdbs.Query('the title ')),
        (webdbs.Query('The Title'), webdbs.Query(' the title')),
        (webdbs.Query('The Title'), webdbs.Query(' the title ')),
        (webdbs.Query('The Title'), webdbs.Query('the  title')),
        (webdbs.Query('The Title'), webdbs.Query('the  title ')),
        (webdbs.Query('The Title'), webdbs.Query(' the title')),
        (webdbs.Query('The Title', year='2000'), webdbs.Query('The Title', year='2000')),
        (webdbs.Query('The Title', type=Type.movie), webdbs.Query('The Title', type=Type.movie)),
        (webdbs.Query('The Title', type=Type.series), webdbs.Query('The Title', type=Type.series)),
        (webdbs.Query('The Title', type=Type.series, year=2000), webdbs.Query('The Title', type=Type.series, year=2000)),
    ),
    ids=lambda value: str(value),
)
def test_Query_equality(a, b):
    assert a == b
    assert b == a

@pytest.mark.parametrize(
    argnames=('a', 'b'),
    argvalues=(
        (webdbs.Query('The Title'), webdbs.Query('The Title 2')),
        (webdbs.Query('The Title', year='2000'), webdbs.Query('The Title', year='2001')),
        (webdbs.Query('The Title', type=Type.movie), webdbs.Query('The Title', type=Type.series)),
        (webdbs.Query('The Title', type=Type.series, year=2000), webdbs.Query('The Title', type=Type.movie, year=2000)),
        (webdbs.Query('The Title', type=Type.series, year=2000), webdbs.Query('The Title', type=Type.series, year=2001)),
        (webdbs.Query('The Title', type=Type.series, year=2000), webdbs.Query('The Title', type=Type.movie, year=2001)),
    ),
    ids=lambda value: str(value),
)
def test_Query_inequality(a, b):
    assert a != b
    assert b != a

@pytest.mark.parametrize(
    argnames=('query', 'exp_string'),
    argvalues=(
        (webdbs.Query('The Title'), 'The Title'),
        (webdbs.Query('The Title', type=Type.movie), 'The Title type:movie'),
        (webdbs.Query('The Title', type=Type.series), 'The Title type:series'),
        (webdbs.Query('The Title', type=Type.movie, year='2010'), 'The Title year:2010 type:movie'),
    ),
    ids=lambda value: str(value),
)
def test_Query_as_string(query, exp_string):
    assert str(query) == exp_string

@pytest.mark.parametrize(
    argnames=('string', 'exp_query'),
    argvalues=(
        ('The Title', webdbs.Query('The Title')),
        ('The Title type:movie', webdbs.Query('The Title', type=Type.movie)),
        ('The Title type:season', webdbs.Query('The Title', type=Type.season)),
        ('The Title type:episode', webdbs.Query('The Title', type=Type.episode)),
        ('The Title type:series', webdbs.Query('The Title', type=Type.series)),
        ('The Title year:2000', webdbs.Query('The Title', year='2000')),
        ('The Title year:2003', webdbs.Query('The Title', year='2003')),
        ('The Title type:movie year:2000', webdbs.Query('The Title', type=Type.movie, year='2000')),
        ('The Title type:series year:2003', webdbs.Query('The Title', type=Type.series, year='2003')),
        ('The Title type:film', webdbs.Query('The Title', type=Type.movie)),
        ('The Title type:tv', webdbs.Query('The Title', type=Type.series)),
        ('The Title type:show', webdbs.Query('The Title', type=Type.series)),
        ('The Title type:tvshow', webdbs.Query('The Title', type=Type.series)),
        ('The Title type:season', webdbs.Query('The Title', type=Type.season)),
        ('The Title type:episode', webdbs.Query('The Title', type=Type.episode)),
    ),
)
def test_Query_from_string(string, exp_query):
    assert webdbs.Query.from_string(string) == exp_query

@pytest.mark.parametrize(
    argnames=('string', 'exp_query'),
    argvalues=(
        ('The Title type:foo', webdbs.Query('The Title type:foo')),
        ('The Title year:bar', webdbs.Query('The Title year:bar')),
    ),
)
def test_Query_from_string_with_unknown_keyword_value(string, exp_query):
    assert webdbs.Query.from_string(string) == exp_query

@pytest.mark.parametrize(
    argnames=('path', 'exp_query'),
    argvalues=(
        ('path/to/The Title', webdbs.Query('The Title', type=Type.movie)),
        ('path/to/The Title 2015', webdbs.Query('The Title', type=Type.movie, year='2015')),
        ('path/to/The Title S04', webdbs.Query('The Title', type=Type.season)),
        ('path/to/The Title 2015 S04', webdbs.Query('The Title', type=Type.season, year='2015')),
        ('path/to/The Title S04E03', webdbs.Query('The Title', type=Type.episode)),
        ('path/to/The Title 2015 S04E03', webdbs.Query('The Title', type=Type.episode, year='2015')),
    ),
)
def test_Query_from_path(path, exp_query):
    assert webdbs.Query.from_path(path) == exp_query


@pytest.mark.parametrize(
    argnames=('query', 'exp_repr'),
    argvalues=(
        (webdbs.Query('The Title'), "Query(title='The Title')"),
        (webdbs.Query('The Title', type=Type.movie), "Query(title='The Title', type=Type.movie)"),
        (webdbs.Query('The Title', year='1999'), "Query(title='The Title', year='1999')"),
        (webdbs.Query('The Title', type=Type.series, year='1999'), "Query(title='The Title', year='1999', type=Type.series)"),
    ),
    ids=lambda value: str(value),
)
def test_Query_as_repr(query, exp_repr):
    assert repr(query) == exp_repr


def test_SearchResult_with_all_info():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'type' : Type.movie,
        'year' : '2000',
        'title' : 'Foo',
        'title_original' : 'Le Foo',
        'title_english' : 'Fucking Foo',
        'keywords' : ('foo', 'some bar'),
        'cast' : ('This Guy', 'That Dude'),
        'summary' : 'I dunno.',
        'country' : 'Antarctica',
    }
    sr = webdbs.SearchResult(**info)
    for k, v in info.items():
        assert getattr(sr, k) == v

def test_SearchResult_with_only_mandatory_info():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'type' : Type.series,
        'year' : '2000',
        'title' : 'Foo',
    }
    sr = webdbs.SearchResult(**info)
    for k, v in info.items():
        assert getattr(sr, k) == v

def test_SearchResult_with_lacking_mandatory_info():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'type' : Type.season,
        'year' : '2000',
        'title' : 'Foo',
    }
    for k in info:
        info_ = info.copy()
        del info_[k]
        with pytest.raises(TypeError, match=rf'missing 1 required keyword-only argument: {k!r}'):
            webdbs.SearchResult(**info_)

def test_SearchResult_with_valid_type():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'year' : '2000',
        'title' : 'Foo',
    }
    for type in tuple(Type):
        sr = webdbs.SearchResult(type=type, **info)
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
            webdbs.SearchResult(type=type, **info)

@pytest.mark.parametrize(
    argnames=('id', 'exp_type'),
    argvalues=(
        ('123', str),
        (123.0, float),
        (123, int),
    ),
)
def test_SearchResult_preserves_id_type(id, exp_type):
    info = {
        'id' : id,
        'type': Type.series,
        'url' : 'http://foo.bar/123',
        'year' : '2000',
        'title' : 'Foo',
    }
    result = webdbs.SearchResult(**info)
    assert result.id == id
    assert isinstance(result.id, exp_type)
