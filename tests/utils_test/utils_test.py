import re
from unittest.mock import AsyncMock, Mock, call

import pytest

from upsies import utils


def test_cached_property_caches_return_value_of_decorated_function():
    calculation_mock = Mock()
    calculation_mock.return_value = 'expensive result'

    class Foo():
        @utils.cached_property
        def bar(self):
            return calculation_mock()

    foo = Foo()
    for _ in range(5):
        assert foo.bar == 'expensive result'
        assert calculation_mock.call_args_list == [call()]
    foo.bar = 'asdf'
    assert foo.bar == 'asdf'


@pytest.mark.asyncio
async def test_asyncmemoize_caches_return_values():
    def a(*args, **kwargs):
        args_str = ', '.join(args)
        kwargs_str = ', '.join(f'{k}={v}' for k, v in kwargs.items())
        return f'a({args_str}, {kwargs_str})'

    def b(*args, **kwargs):
        args_str = ', '.join(args)
        kwargs_str = ', '.join(f'{k}={v}' for k, v in kwargs.items())
        return f'b({args_str}, {kwargs_str})'

    a_mock = AsyncMock(side_effect=a)
    b_mock = AsyncMock(side_effect=b)
    a_memoized = utils.asyncmemoize(a_mock)
    b_memoized = utils.asyncmemoize(b_mock)
    mocks = Mock()
    mocks.attach_mock(a_mock, 'a')
    mocks.attach_mock(b_mock, 'b')

    for _ in range(3):
        assert await a_memoized('foo', bar='baz') == 'a(foo, bar=baz)'
        assert mocks.mock_calls == [
            call.a('foo', bar='baz'),
        ]

    for _ in range(3):
        assert await a_memoized('this', that='what') == 'a(this, that=what)'
        assert mocks.mock_calls == [
            call.a('foo', bar='baz'),
            call.a('this', that='what'),
        ]

    for _ in range(3):
        assert await b_memoized('this', that='what') == 'b(this, that=what)'
        assert mocks.mock_calls == [
            call.a('foo', bar='baz'),
            call.a('this', that='what'),
            call.b('this', that='what'),
        ]

    for _ in range(3):
        assert await a_memoized('x', 'y', 'z') == 'a(x, y, z, )'
        assert mocks.mock_calls == [
            call.a('foo', bar='baz'),
            call.a('this', that='what'),
            call.b('this', that='what'),
            call.a('x', 'y', 'z'),
        ]

@pytest.mark.asyncio
async def test_asyncmemoize_clear_cache():
    def a(*args, **kwargs):
        args_str = ', '.join(args)
        kwargs_str = ', '.join(f'{k}={v}' for k, v in kwargs.items())
        return f'a({args_str}, {kwargs_str})'

    def b(*args, **kwargs):
        args_str = ', '.join(args)
        kwargs_str = ', '.join(f'{k}={v}' for k, v in kwargs.items())
        return f'b({args_str}, {kwargs_str})'

    a_mock = AsyncMock(side_effect=a)
    b_mock = AsyncMock(side_effect=b)
    a_memoized = utils.asyncmemoize(a_mock)
    b_memoized = utils.asyncmemoize(b_mock)
    mocks = Mock()
    mocks.attach_mock(a_mock, 'a')
    mocks.attach_mock(b_mock, 'b')

    for _ in range(3):
        assert await a_memoized('foo', bar='baz') == 'a(foo, bar=baz)'
        assert mocks.mock_calls == [
            call.a('foo', bar='baz'),
        ]

    for _ in range(3):
        assert await b_memoized('this', that='what') == 'b(this, that=what)'
        assert mocks.mock_calls == [
            call.a('foo', bar='baz'),
            call.b('this', that='what'),
        ]

    a_memoized.clear_cache()

    for _ in range(3):
        assert await a_memoized('foo', bar='baz') == 'a(foo, bar=baz)'
        assert mocks.mock_calls == [
            call.a('foo', bar='baz'),
            call.b('this', that='what'),
            call.a('foo', bar='baz'),
        ]

    for _ in range(3):
        assert await b_memoized('this', that='what') == 'b(this, that=what)'
        assert mocks.mock_calls == [
            call.a('foo', bar='baz'),
            call.b('this', that='what'),
            call.a('foo', bar='baz'),
        ]

    b_memoized.clear_cache()

    for _ in range(3):
        assert await b_memoized('this', that='what') == 'b(this, that=what)'
        assert mocks.mock_calls == [
            call.a('foo', bar='baz'),
            call.b('this', that='what'),
            call.a('foo', bar='baz'),
            call.b('this', that='what'),
        ]

@pytest.mark.asyncio
async def test_asyncmemoize_caches_exceptions():
    def a(exccls, *args, **kwargs):
        args_str = ', '.join(args)
        kwargs_str = ', '.join(f'{k}={v}' for k, v in kwargs.items())
        raise exccls(f'a({args_str}, {kwargs_str})')

    def b(exccls, *args, **kwargs):
        args_str = ', '.join(args)
        kwargs_str = ', '.join(f'{k}={v}' for k, v in kwargs.items())
        raise exccls(f'b({args_str}, {kwargs_str})')

    a_mock = AsyncMock(side_effect=a)
    b_mock = AsyncMock(side_effect=b)
    a_memoized = utils.asyncmemoize(a_mock)
    b_memoized = utils.asyncmemoize(b_mock)
    mocks = Mock()
    mocks.attach_mock(a_mock, 'a')
    mocks.attach_mock(b_mock, 'b')

    for _ in range(3):
        with pytest.raises(RuntimeError, match=r'a\(foo, bar=baz\)'):
            await a_memoized(RuntimeError, 'foo', bar='baz')
        assert mocks.mock_calls == [
            call.a(RuntimeError, 'foo', bar='baz'),
        ]

    for _ in range(3):
        with pytest.raises(TypeError, match=r'a\(this, that=what\)'):
            await a_memoized(TypeError, 'this', that='what')
        assert mocks.mock_calls == [
            call.a(RuntimeError, 'foo', bar='baz'),
            call.a(TypeError, 'this', that='what'),
        ]

    for _ in range(3):
        with pytest.raises(BaseException, match=r'b\(this, that=what\)'):
            await b_memoized(BaseException, 'this', that='what')
        assert mocks.mock_calls == [
            call.a(RuntimeError, 'foo', bar='baz'),
            call.a(TypeError, 'this', that='what'),
            call.b(BaseException, 'this', that='what'),
        ]

    for _ in range(3):
        with pytest.raises(ValueError, match=r'a\(x, y, z, \)'):
            await a_memoized(ValueError, 'x', 'y', 'z')
        assert mocks.mock_calls == [
            call.a(RuntimeError, 'foo', bar='baz'),
            call.a(TypeError, 'this', that='what'),
            call.b(BaseException, 'this', that='what'),
            call.a(ValueError, 'x', 'y', 'z'),
        ]

def test_asyncmemoize_properly_wraps_function():
    def a(exccls, *args, **kwargs):
        """This is a()"""

    a_memoized = utils.asyncmemoize(a)
    assert a_memoized.__module__ is a.__module__
    assert a_memoized.__name__ is a.__name__
    assert a_memoized.__qualname__ is a.__qualname__
    assert a_memoized.__annotations__ is a.__annotations__
    assert a_memoized.__doc__ is a.__doc__
    assert a_memoized.__wrapped__ is a


def test_asyncontextmanager():
    import sys

    from upsies.utils import asynccontextmanager

    if sys.version_info < (3, 7):
        import async_generator
        assert asynccontextmanager is async_generator.asynccontextmanager
    else:
        import contextlib
        assert asynccontextmanager is contextlib.asynccontextmanager
        with pytest.raises(ImportError):
            import async_generator


def test_submodules_finds_modules_and_packages(mocker):
    mocker.patch('os.listdir', return_value=(
        '_this_is_private',
        'this_is_a_package',
        'this_is_a_module.py',
        'this_is_something_else.foo',
    ))
    import_mock = mocker.patch('importlib.import_module', side_effect=(1, 2, 3, 4, 5))
    assert set(utils.submodules('asdf')) == {1, 2}
    assert import_mock.call_args_list == [
        call(name='.this_is_a_package', package='asdf'),
        call(name='.this_is_a_module', package='asdf'),
    ]


def test_subclasses():
    from aiobtclientapi.clients import (APIBase, deluge, qbittorrent, rtorrent,
                                        transmission)
    subclses = utils.subclasses(
        basecls=APIBase,
        modules={deluge, qbittorrent, rtorrent, transmission},
    )
    assert subclses == {
        deluge.DelugeAPI,
        qbittorrent.QbittorrentAPI,
        rtorrent.RtorrentAPI,
        transmission.TransmissionAPI,
    }


def test_closest_number():
    assert utils.closest_number(5, ()) == 0
    assert utils.closest_number(5, (), default=123) == 123

    numbers = (10, 20, 30)

    for n in (-10, 0, 9, 10, 11, 14):
        assert utils.closest_number(n, numbers) == 10
    for n in (16, 19, 20, 21, 24):
        assert utils.closest_number(n, numbers) == 20
    for n in range(26, 50):
        assert utils.closest_number(n, numbers) == 30

    for n in range(0, 50):
        with pytest.raises(ValueError, match=r'^No number equal to or below 9: \(10, 20, 30\)$'):
            utils.closest_number(n, numbers, max=9)

    for n in range(0, 50):
        assert utils.closest_number(n, numbers, max=10) == 10

    for n in range(0, 16):
        assert utils.closest_number(n, numbers, max=20) == 10
    for n in range(16, 50):
        assert utils.closest_number(n, numbers, max=20) == 20


def test_CaseInsensitiveString_equality():
    assert utils.CaseInsensitiveString('Foo') == 'foo'
    assert utils.CaseInsensitiveString('fOo') == 'FOO'
    assert utils.CaseInsensitiveString('foO') == 'foo'
    assert utils.CaseInsensitiveString('foo') != 'fooo'

def test_CaseInsensitiveString_identity():
    assert utils.CaseInsensitiveString('Foo') in ('foo', 'bar', 'baz')
    assert utils.CaseInsensitiveString('fOo') in ('FOO', 'BAR', 'BAZ')
    assert utils.CaseInsensitiveString('foO') not in ('fooo', 'bar', 'baz')

def test_CaseInsensitiveString_lt():
    assert utils.CaseInsensitiveString('foo') < 'Fooo'

def test_CaseInsensitiveString_le():
    assert utils.CaseInsensitiveString('foo') <= 'Foo'

def test_CaseInsensitiveString_gt():
    assert utils.CaseInsensitiveString('Fooo') > 'foo'

def test_CaseInsensitiveString_ge():
    assert utils.CaseInsensitiveString('Foo') >= 'foo'


def test_MonitoredList_getitem():
    lst = utils.MonitoredList((1, 2, 3), callback=Mock())
    assert lst[0] == 1
    assert lst[1] == 2
    assert lst[2] == 3

def test_MonitoredList_setitem():
    cb = Mock()
    lst = utils.MonitoredList((1, 2, 3), callback=cb)
    assert cb.call_args_list == []
    lst[0] = 100
    assert cb.call_args_list == [call(lst)]
    assert lst == [100, 2, 3]

def test_MonitoredList_delitem():
    cb = Mock()
    lst = utils.MonitoredList((1, 2, 3), callback=cb)
    assert cb.call_args_list == []
    del lst[1]
    assert cb.call_args_list == [call(lst)]
    assert lst == [1, 3]

def test_MonitoredList_insert():
    cb = Mock()
    lst = utils.MonitoredList((1, 2, 3), callback=cb)
    assert cb.call_args_list == []
    lst.insert(1, 1.5)
    assert cb.call_args_list == [call(lst)]
    assert lst == [1, 1.5, 2, 3]

def test_MonitoredList_len():
    lst = utils.MonitoredList((1, 2, 3), callback=Mock())
    assert len(lst) == 3

def test_MonitoredList_equality():
    lst = utils.MonitoredList((1, 2, 3), callback=Mock())
    assert lst == [1, 2, 3]
    assert lst != [1, 2, 4]
    assert lst == utils.MonitoredList([1, 2, 3], callback=Mock())
    assert lst != utils.MonitoredList([1, 3, 2], callback=Mock())

def test_MonitoredList_repr():
    cb = Mock()
    lst = utils.MonitoredList((1, 2, 3), callback=cb)
    assert repr(lst) == f'MonitoredList([1, 2, 3], callback={cb!r})'


def test_RestrictedMapping_init_with_defaults():
    dct = utils.RestrictedMapping({'a': 1, 'b': 2, 'c': 3})
    assert dct._allowed_keys == {'a', 'b', 'c'}
    assert dct == {'a': 1, 'b': 2, 'c': 3}

def test_RestrictedMapping_init_with_allowed_keys():
    dct = utils.RestrictedMapping(allowed_keys=('a', 'b', 'c'), a=1)
    assert dct._allowed_keys == {'a', 'b', 'c'}
    assert dct == {'a': 1}

def test_RestrictedMapping_getitem():
    dct = utils.RestrictedMapping(allowed_keys=('a', 'b', 'c'), a=1, b=2, c=3)
    assert dct == {'a': 1, 'b': 2, 'c': 3}

def test_RestrictedMapping_setitem():
    dct = utils.RestrictedMapping(allowed_keys=('a', 'b', 'c'))
    dct['a'] = 'foo'
    assert dct == {'a': 'foo'}
    dct['b'] = 'bar'
    assert dct == {'a': 'foo', 'b': 'bar'}
    with pytest.raises(KeyError, match=r"^'baz'$"):
        dct['baz'] = 'c'

def test_RestrictedMapping_delitem():
    dct = utils.RestrictedMapping(allowed_keys=('a', 'b', 'c'), a=1, b=2)
    assert dct == {'a': 1, 'b': 2}
    del dct['b']
    assert dct == {'a': 1}
    with pytest.raises(KeyError, match=r"^'c'$"):
        del dct['c']
    with pytest.raises(KeyError, match=r"^'baz'$"):
        del dct['baz']

def test_RestrictedMapping_iter():
    dct = utils.RestrictedMapping(allowed_keys=('a', 'b', 'c'), a=1, b=2)
    assert tuple(iter(dct)) == ('a', 'b')

def test_RestrictedMapping_len():
    dct = utils.RestrictedMapping(allowed_keys=('a', 'b', 'c'), a=1, b=2)
    assert len(dct) == 2

def test_RestrictedMapping_repr():
    dct = utils.RestrictedMapping(allowed_keys=('a', 'b', 'c'), a=1, b=2)
    assert repr(dct) == repr({'a': 1, 'b': 2})


def test_is_sequence():
    assert utils.is_sequence((1, 2, 3))
    assert utils.is_sequence([1, 2, 3])
    assert not utils.is_sequence('123')


@pytest.mark.parametrize(
    argnames=('a', 'b', 'merged'),
    argvalues=(
        ({1: 10}, {1: 20}, {1: 20}),
        ({1: 10}, {2: 20}, {1: 10, 2: 20}),
        ({1: 10}, {1: 20, 2: 2000}, {1: 20, 2: 2000}),
        ({1: 10, 2: 2000}, {1: 20}, {1: 20, 2: 2000}),
        ({1: {2: 20}}, {1: {2: 2000}}, {1: {2: 2000}}),
        ({1: {2: 20}}, {1: {2: {3: 30}}}, {1: {2: {3: 30}}}),
        ({1: {2: 20, 3: {5: 50}}}, {1: {3: {4: 40, 5: 5000}}}, {1: {2: 20, 3: {4: 40, 5: 5000}}}),
    ),
    ids=lambda v: str(v),
)
def test_merge_dicts(a, b, merged):
    assert utils.merge_dicts(a, b) == merged
    assert id(a) != id(merged)
    assert id(b) != id(merged)


def test_deduplicate_deduplicates():
    assert utils.deduplicate([1, 2, 1, 3, 1, 4, 3, 5]) == [1, 2, 3, 4, 5]

def test_deduplicate_maintains_order():
    assert utils.deduplicate([3, 2, 1, 1, 4, 5, 1, 3]) == [3, 2, 1, 4, 5]

def test_deduplicate_deduplicates_unhashable_items():
    items = [
        {'a': 1, 'b': 2},
        {'a': 2, 'b': 2},
        {'a': 3, 'b': 1},
        {'a': 4, 'b': 3},
        {'a': 5, 'b': 1},
        {'a': 6, 'b': 4},
    ]
    assert utils.deduplicate(items, key=lambda item: item['b']) == [
        {'a': 1, 'b': 2},
        {'a': 3, 'b': 1},
        {'a': 4, 'b': 3},
        {'a': 6, 'b': 4},
    ]


@pytest.mark.parametrize(
    argnames=('items', 'group_sizes', 'exp_groups'),
    argvalues=(
        (range(18), [1], [(0,), (1,), (2,), (3,), (4,), (5,), (6,), (7,), (8,), (9,), (10,), (11,), (12,), (13,), (14,), (15,), (16,), (17,)]),
        (range(18), [1, 2], [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9), (10, 11), (12, 13), (14, 15), (16, 17)]),
        (range(18), [1, 2, 3], [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9, 10, 11), (12, 13, 14), (15, 16, 17)]),
        (range(18), [1, 2, 3, 4], [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9, 10, 11), (12, 13, 14), (15, 16, 17)]),
        (range(18), [1, 2, 3, 4, 5, 6], [(0, 1, 2, 3, 4, 5), (6, 7, 8, 9, 10, 11), (12, 13, 14, 15, 16, 17)]),

        (range(17), [1], [(0,), (1,), (2,), (3,), (4,), (5,), (6,), (7,), (8,), (9,), (10,), (11,), (12,), (13,), (14,), (15,), (16,)]),
        (range(17), [1, 2], [(0,), (1,), (2,), (3,), (4,), (5,), (6,), (7,), (8,), (9,), (10,), (11,), (12,), (13,), (14,), (15,), (16,)]),
        (range(17), [1, 2, 3], [(0,), (1,), (2,), (3,), (4,), (5,), (6,), (7,), (8,), (9,), (10,), (11,), (12,), (13,), (14,), (15,), (16,)]),
        (range(17), [2, 3, 4], [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9, 10, 11), (12, 13, 14), (15, 16, -1)]),
        (range(17), [3, 4], [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9, 10, 11), (12, 13, 14), (15, 16, -1)]),
        (range(17), [4], [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11), (12, 13, 14, 15), (16, -1, -1, -1)]),
        (range(17), [4, 5], [(0, 1, 2, 3, 4), (5, 6, 7, 8, 9), (10, 11, 12, 13, 14), (15, 16, -1, -1, -1)]),

        (range(16), [4], [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11), (12, 13, 14, 15)]),
        (range(16), [5, 4], [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11), (12, 13, 14, 15)]),
        (range(16), [4, 5, 3], [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11), (12, 13, 14, 15)]),
    ),
)
def test_as_groups(items, group_sizes, exp_groups):
    groups = tuple(utils.as_groups(items, group_sizes=group_sizes, default=-1))
    assert len(groups) == len(exp_groups)
    for a, b in zip(groups, exp_groups):
        assert a == b


@pytest.mark.parametrize(
    argnames='object, exp_return_value',
    argvalues=(
        ('foo', False),
        ((1, 2, 3), False),
        (re.compile(r'1, 2, 3'), True),
    ),
)
def test_is_regex_pattern(object, exp_return_value, mocker):
    assert utils.is_regex_pattern(object) is exp_return_value


@pytest.mark.parametrize(
    argnames='obj, exp_id',
    argvalues=(
        # Strings and other simple objects
        ('foo', b'foo'),
        (23, b'23'),
        (2.3, b'2.3'),

        # Iterables
        (['foo', 'bar', 'baz', 4], b'4barbazfoo'),
        (['foo', 'bar', 'baz', (4, 'five')], b'4fivebarbazfoo'),
        ([('foo', 'bar', 'baz'), {'hey': 'ho'}], b'barbazfooheyho'),
        ([('foo', 'bar', 'baz'), {'hey': ['h', 0]}], b'0hheybarbazfoo'),
        ([(1, 2, 3), ('5', 6.0), {7: ['eigh', 't']}], b'12356.07eight'),
        ([(1, 2, 3, (4.1, 4.2)), ('5', 6.0), {7: ['eigh', 't']}], b'1234.14.256.07eight'),

        # Mappings
        ({'a': 1, 'b': 2, 'c': 3}, b'1a2b3c'),
        ({('a', 'b'): 1, 'c': 2}, b'1ab2c'),
        ({('a', 'b', (1, 2)): 'what', 'c': 3}, b'12abwhat3c'),
        ({('a', 'b', (1, (2, 3))): 'what', 'c': 3}, b'123abwhat3c'),
        ({'what': ('a', 'b', (1, (2, 3))), 'c': 3}, b'123abwhat3c'),
    ),
    ids=lambda v: str(v),
)
def test_semantic_hash(obj, exp_id, mocker):
    sha256_mock = mocker.patch('hashlib.sha256')
    assert utils.semantic_hash(obj) == sha256_mock.return_value.hexdigest.return_value
    assert sha256_mock.call_args_list == [call(exp_id)]

@pytest.mark.parametrize(
    argnames='obj',
    argvalues=(
        (i for i in range(10)),
    ),
    ids=lambda v: repr(v),
)
def test_semantic_hash_gets_unsupported_type(obj, mocker):
    sha256_mock = mocker.patch('hashlib.sha256')
    with pytest.raises(RuntimeError, match=rf'Unsupported type: {type(obj)!r}: {obj!r}'):
        utils.semantic_hash(obj)
    assert sha256_mock.call_args_list == []
