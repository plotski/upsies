from unittest.mock import Mock, call

import pytest

from upsies.utils import webdbs
from upsies.utils.types import ReleaseType


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_Query_title():
    q = webdbs.Query()
    cb = Mock()
    q.signal.register('changed', cb)

    for _ in range(3):
        assert q.title == ''
        assert q.title_normalized == ''
        assert cb.mock_calls == []

    for _ in range(3):
        q.title = 'The Title '
        assert q.title_normalized == 'the title'
        assert cb.mock_calls == [call(q)]

    for _ in range(3):
        q.title = '  The\n OTHER  Title! '
        assert q.title_normalized == 'the other title!'
        assert cb.mock_calls == [call(q), call(q)]


def test_Query_year():
    q = webdbs.Query('The Title', year='2000')
    cb = Mock()
    q.signal.register('changed', cb)
    assert q.year == '2000'
    assert cb.mock_calls == []

    for _ in range(3):
        q.year = 2001
        assert q.year == '2001'
        assert cb.mock_calls == [call(q)]

    for _ in range(3):
        q.year = 2001.5
        assert q.year == '2001'
        assert cb.mock_calls == [call(q)]

    with pytest.raises(ValueError, match=r'^Invalid year: 1000$'):
        q.year = 1000
    assert cb.mock_calls == [call(q)]
    with pytest.raises(ValueError, match=r'^Invalid year: 3000$'):
        q.year = '3000'
    assert cb.mock_calls == [call(q)]
    with pytest.raises(ValueError, match=r'^Invalid year: foo$'):
        q.year = 'foo'
    assert cb.mock_calls == [call(q)]


@pytest.mark.parametrize('typ', list(ReleaseType) + [str(t) for t in ReleaseType], ids=lambda v: repr(v))
def test_Query_valid_type(typ):
    q = webdbs.Query('The Title', type=typ)
    cb = Mock()
    q.signal.register('changed', cb)
    assert q.type is ReleaseType(typ)

    all_types = list(ReleaseType)
    if all_types.index(ReleaseType(typ)) < len(all_types) - 1:
        next_type_index = all_types.index(ReleaseType(typ)) + 1
    else:
        next_type_index = 0
    print(typ, all_types, next_type_index)
    next_type = all_types[next_type_index]

    for _ in range(3):
        q.type = next_type
        assert q.type is ReleaseType(next_type)
        assert cb.mock_calls == [call(q)]

    for _ in range(3):
        q.type = typ
        assert q.type is ReleaseType(typ)
        assert cb.mock_calls == [call(q), call(q)]

def test_Query_invalid_type():
    q = webdbs.Query('The Title')
    cb = Mock()
    q.signal.register('changed', cb)
    with pytest.raises(ValueError, match=r"^'foo' is not a valid ReleaseType$"):
        q.type = 'foo'
    assert cb.mock_calls == []


def test_Query_id():
    q = webdbs.Query('The Title', id='12345')
    cb = Mock()
    q.signal.register('changed', cb)
    assert q.id == '12345'
    assert cb.mock_calls == []

    for _ in range(3):
        q.id = 123
        assert q.id == '123'
        assert cb.mock_calls == [call(q)]

    for _ in range(3):
        q.id = 'tt12345'
        assert q.id == 'tt12345'
        assert cb.mock_calls == [call(q), call(q)]


def test_Query_update():
    q = webdbs.Query('The Title', year='2010', type=ReleaseType.series)
    cb = Mock()
    q.signal.register('changed', cb)
    assert cb.call_args_list == []

    for _ in range(3):
        q.update(webdbs.Query('The Title', type=ReleaseType.movie))
        assert str(q) == 'The Title type:movie'
        assert cb.call_args_list == [call(q)]

    for _ in range(3):
        q.update(webdbs.Query('The Title', type=ReleaseType.season))
        assert str(q) == 'The Title type:season'
        assert cb.call_args_list == [call(q), call(q)]

    for _ in range(3):
        q.update(webdbs.Query('The Other Title', type=ReleaseType.episode, year='2015'))
        assert str(q) == 'The Other Title year:2015 type:episode'
        assert cb.call_args_list == [call(q), call(q), call(q)]

    for _ in range(3):
        q.update(webdbs.Query('The Title', id='123', year='2015', type=ReleaseType.episode))
        assert str(q) == 'id:123'
        assert cb.call_args_list == [call(q), call(q), call(q), call(q)]


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
        (webdbs.Query('The Title', type=ReleaseType.movie), webdbs.Query('The Title', type=ReleaseType.movie)),
        (webdbs.Query('The Title', type=ReleaseType.series), webdbs.Query('The Title', type=ReleaseType.series)),
        (webdbs.Query('The Title', type=ReleaseType.episode, year=2000), webdbs.Query('The Title', type=ReleaseType.episode, year=2000)),
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
        (webdbs.Query(id=123), webdbs.Query(id=124)),
        (webdbs.Query('The Title', year='2000'), webdbs.Query('The Title', year='2001')),
        (webdbs.Query('The Title', type=ReleaseType.movie), webdbs.Query('The Title', type=ReleaseType.series)),
        (webdbs.Query('The Title', type=ReleaseType.series, year=2000), webdbs.Query('The Title', type=ReleaseType.movie, year=2000)),
        (webdbs.Query('The Title', type=ReleaseType.series, year=2000), webdbs.Query('The Title', type=ReleaseType.series, year=2001)),
        (webdbs.Query('The Title', type=ReleaseType.series, year=2000), webdbs.Query('The Title', type=ReleaseType.movie, year=2001)),
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
        (webdbs.Query('The Title', type=ReleaseType.movie), 'The Title type:movie'),
        (webdbs.Query('The Title', type=ReleaseType.series), 'The Title type:season'),
        (webdbs.Query('The Title', type=ReleaseType.movie, year='2010'), 'The Title type:movie year:2010'),
        (webdbs.Query('The Title', year='2010', type=ReleaseType.movie), 'The Title year:2010 type:movie'),
        (webdbs.Query('The Title', id='123', year='2010', type=ReleaseType.movie), 'id:123'),
    ),
    ids=lambda value: str(value),
)
def test_Query_as_string(query, exp_string):
    assert str(query) == exp_string

@pytest.mark.parametrize(
    argnames=('string', 'exp_query'),
    argvalues=(
        ('The Title', webdbs.Query('The Title')),
        ('The Title type:movie', webdbs.Query('The Title', type=ReleaseType.movie)),
        ('The Title type:season', webdbs.Query('The Title', type=ReleaseType.season)),
        ('The Title type:episode', webdbs.Query('The Title', type=ReleaseType.episode)),
        ('The Title type:series', webdbs.Query('The Title', type=ReleaseType.series)),
        ('The Title year:2000', webdbs.Query('The Title', year='2000')),
        ('The Title year:2003', webdbs.Query('The Title', year='2003')),
        ('The Title type:movie year:2000', webdbs.Query('The Title', type=ReleaseType.movie, year='2000')),
        ('The Title type:series year:2003', webdbs.Query('The Title', type=ReleaseType.series, year='2003')),
        ('The Title type:film', webdbs.Query('The Title', type=ReleaseType.movie)),
        ('The Title type:tv', webdbs.Query('The Title', type=ReleaseType.series)),
        ('The Title type:show', webdbs.Query('The Title', type=ReleaseType.series)),
        ('The Title type:tvshow', webdbs.Query('The Title', type=ReleaseType.series)),
        ('The Title id:foo', webdbs.Query('The Title', id='foo')),
        ('id:foo', webdbs.Query(id='foo')),
        ('id:foo year:2005', webdbs.Query(id='foo', year='2005')),
    ),
    ids=lambda v: str(v),
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
        ('path/to/The Title', webdbs.Query('The Title', type=ReleaseType.movie)),
        ('path/to/The Title 2015', webdbs.Query('The Title', type=ReleaseType.movie, year='2015')),
        ('path/to/The Title S04', webdbs.Query('The Title', type=ReleaseType.season)),
        ('path/to/The Title 2015 S04', webdbs.Query('The Title', type=ReleaseType.season, year='2015')),
        ('path/to/The Title S04E03', webdbs.Query('The Title', type=ReleaseType.episode)),
        ('path/to/The Title 2015 S04E03', webdbs.Query('The Title', type=ReleaseType.episode, year='2015')),
    ),
)
def test_Query_from_path(path, exp_query):
    assert webdbs.Query.from_path(path) == exp_query


@pytest.mark.parametrize(
    argnames=('query', 'exp_repr'),
    argvalues=(
        (webdbs.Query('The Title'),
         "Query(title='The Title')"),
        (webdbs.Query('The Title', type=ReleaseType.movie),
         "Query(title='The Title', type=ReleaseType.movie)"),
        (webdbs.Query('The Title', year='1999'),
         "Query(title='The Title', year='1999')"),
        (webdbs.Query('The Title', type=ReleaseType.season, year='1999'),
         "Query(title='The Title', year='1999', type=ReleaseType.season)"),
        (webdbs.Query('The Title', type=ReleaseType.season, year='1999', id='123'),
         "Query(title='The Title', year='1999', type=ReleaseType.season, id='123')"),
    ),
    ids=lambda value: str(value),
)
def test_Query_as_repr(query, exp_repr):
    assert repr(query) == exp_repr


def test_SearchResult_with_all_info():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'type' : ReleaseType.movie,
        'year' : '2000',
        'title' : 'Foo',
        'title_original' : 'Le Foo',
        'title_english' : 'Fucking Foo',
        'genres' : ('foo', 'some bar'),
        'cast' : ('This Guy', 'That Dude'),
        'summary' : 'I dunno.',
        'countries' : ('Antarctica',),
    }
    sr = webdbs.SearchResult(**info)
    for k, v in info.items():
        assert getattr(sr, k) == v

def test_SearchResult_with_only_mandatory_info():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'type' : ReleaseType.series,
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
        'type' : ReleaseType.season,
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
    for type in tuple(ReleaseType) + tuple(str(t) for t in ReleaseType):
        sr = webdbs.SearchResult(type=type, **info)
        assert sr.type == ReleaseType(type)

def test_SearchResult_with_invalid_type():
    info = {
        'id' : '123',
        'url' : 'http://foo.bar/123',
        'year' : '2000',
        'title' : 'Foo',
    }
    for type in ('foo', 'bar', 'baz', None):
        with pytest.raises(ValueError, match=rf'{type!r} is not a valid ReleaseType'):
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
        'type': ReleaseType.series,
        'url' : 'http://foo.bar/123',
        'year' : '2000',
        'title' : 'Foo',
    }
    result = webdbs.SearchResult(**info)
    assert result.id == id
    assert isinstance(result.id, exp_type)

@pytest.mark.parametrize(
    argnames=('countries', 'exp_countries'),
    argvalues=(
        (['US'], ('United States',)),
        (AsyncMock(return_value=['US']), ('United States',)),
    ),
)
@pytest.mark.asyncio
async def test_SearchResult_normalizes_countries(countries, exp_countries):
    info = {
        'id' : id,
        'type': ReleaseType.series,
        'url' : 'http://foo.bar/123',
        'year' : '2000',
        'title' : 'Foo',
        'countries': countries,
    }
    result = webdbs.SearchResult(**info)
    if callable(result.countries):
        countries = await result.countries()
    else:
        countries = result.countries
    assert countries == exp_countries


def test_Person():
    assert isinstance(webdbs.Person('Foo Bar'), str)
    assert webdbs.Person('Foo Bar').url == ''
    assert webdbs.Person('Foo Bar', url='http://foo').url == 'http://foo'
