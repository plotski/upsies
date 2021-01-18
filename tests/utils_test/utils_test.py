import sys
from unittest.mock import Mock, call

import pytest

from upsies import utils


@pytest.mark.skipif(sys.version_info < (3, 8, 0), reason='Python 3.8 functools includes cached_property')
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


@pytest.mark.parametrize(
    argnames=('name', 'bool_value'),
    argvalues=(
        ('movie', True),
        ('series', True),
        ('season', True),
        ('episode', True),
        ('unknown', False),
    ),
)
def test_ReleaseType_truthiness(name, bool_value):
    assert bool(getattr(utils.ReleaseType, name)) is bool_value

@pytest.mark.parametrize('name', utils.ReleaseType.__members__)
def test_ReleaseType_string(name):
    assert str(getattr(utils.ReleaseType, name)) == name

@pytest.mark.parametrize('name', utils.ReleaseType.__members__)
def test_ReleaseType_repr(name):
    assert repr(getattr(utils.ReleaseType, name)) == f'ReleaseType.{name}'


def test_submodules_finds_modules_and_packages():
    import importlib
    assert set(utils.submodules('upsies.utils')) == {
        importlib.import_module('upsies.utils.browser'),
        importlib.import_module('upsies.utils.btclients'),
        importlib.import_module('upsies.utils.configfiles'),
        importlib.import_module('upsies.utils.country'),
        importlib.import_module('upsies.utils.daemon'),
        importlib.import_module('upsies.utils.fs'),
        importlib.import_module('upsies.utils.html'),
        importlib.import_module('upsies.utils.http'),
        importlib.import_module('upsies.utils.imghosts'),
        importlib.import_module('upsies.utils.release'),
        importlib.import_module('upsies.utils.screenshot'),
        importlib.import_module('upsies.utils.signal'),
        importlib.import_module('upsies.utils.subproc'),
        importlib.import_module('upsies.utils.timestamp'),
        importlib.import_module('upsies.utils.torrent'),
        importlib.import_module('upsies.utils.types'),
        importlib.import_module('upsies.utils.video'),
        importlib.import_module('upsies.utils.webdbs'),
    }


def test_subclasses():
    from upsies.utils import btclients
    from upsies.utils.btclients import dummy, transmission
    subclses = utils.subclasses(
        basecls=btclients.ClientApiBase,
        modules=[dummy, transmission],
    )
    assert subclses == [
        dummy.DummyClientApi,
        transmission.TransmissionClientApi,
    ]


def test_closest_number():
    numbers = (10, 20, 30)
    for n in (-10, 0, 9, 10, 11, 14):
        assert utils.closest_number(n, numbers) == 10
    for n in (16, 19, 20, 21, 24):
        assert utils.closest_number(n, numbers) == 20
    for n in range(26, 50):
        assert utils.closest_number(n, numbers) == 30


def test_pretty_bytes():
    assert utils.pretty_bytes(1023) == '1023 B'
    assert utils.pretty_bytes(1024) == '1.00 KiB'
    assert utils.pretty_bytes(1024 + 1024 / 2) == '1.50 KiB'
    assert utils.pretty_bytes((1024**2) - 102.4) == '1023.90 KiB'
    assert utils.pretty_bytes(1024**2) == '1.00 MiB'
    assert utils.pretty_bytes((1024**3) * 123) == '123.00 GiB'
    assert utils.pretty_bytes((1024**4) * 456) == '456.00 TiB'
    assert utils.pretty_bytes((1024**5) * 456) == '456.00 PiB'


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
