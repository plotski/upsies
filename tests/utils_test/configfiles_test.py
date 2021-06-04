import collections
import configparser
import os
from unittest.mock import call, patch

import pytest

from upsies import errors
from upsies.utils.configfiles import (ConfigFiles, _any2list, _any2string,
                                      _ConfigDict)


@pytest.mark.parametrize(
    argnames=('value', 'exp_value'),
    argvalues=(
        (['a', 'b', 'c'], ['a', 'b', 'c']),
        (('a', 'b', 'c'), ['a', 'b', 'c']),
        (iter(('a', 'b', 'c')), ['a', 'b', 'c']),
        ('a b c', ['a', 'b', 'c']),
        ('abc def', ['abc', 'def']),
        (123, ['123']),
    ),
    ids=lambda value: str(value),
)
def test_any2list(value, exp_value):
    assert _any2list(value) == exp_value

@pytest.mark.parametrize(
    argnames=('value', 'exp_value'),
    argvalues=(
        ('a b c', 'a b c'),
        (123, '123'),
        (['a', 'b', 'c'], 'a b c'),
        (('a', 'b', 'c'), 'a b c'),
        (iter(('a', 'b', 'c')), 'a b c'),
    ),
    ids=lambda value: str(value),
)
def test_any2string(value, exp_value):
    assert _any2string(value) == exp_value


@pytest.mark.parametrize(argnames='cls', argvalues=(dict, collections.abc.Mapping))
def test_ConfigDict_subclass(cls):
    d = _ConfigDict({'foo': 'baz'})
    assert isinstance(d, cls)

def test_ConfigDict_implements_delitem():
    d = _ConfigDict({'foo': 'bar', 'bar': 'abc'})
    del d['bar']
    assert d == {'foo': 'bar'}

def test_ConfigDict_implements_len():
    d = _ConfigDict({'foo': 'baz', 'bar': 'xyz'})
    assert len(d) == 2

def test_ConfigDict_implements_repr():
    d = _ConfigDict({'foo': 'baz', 'bar': 'xyz'})
    assert repr(d) == repr({'foo': 'baz', 'bar': 'xyz'})

def test_ConfigDict_implements_getitem():
    d = _ConfigDict({'foo': 'bar', 'baz': 123})
    assert d['foo'] == 'bar'
    assert d['baz'] == 123

def test_ConfigDict_implements_setitem():
    d = _ConfigDict({'foo': 'bar', 'baz': 123})
    d['foo'] = 'hello'
    d['baz'] = 'world'
    assert d == {'foo': 'hello', 'baz': 'world'}

def test_ConfigDict_raises_KeyError_when_setting_unknown_key():
    d = _ConfigDict({'foo': 'bar'})
    with pytest.raises(KeyError, match=r"^'asdf'$"):
        d['asdf'] = 'hello'

def test_ConfigDict_with_custom_keys():
    d = _ConfigDict({'foo': 'bar'}, keys={'foo': None, 'bar': None, 123: None})
    d['foo'] = 'asdf'
    d['bar'] = 'baz'
    d[123] = '456'
    assert d == {'foo': 'asdf', 'bar': 'baz', 123: '456'}
    with pytest.raises(KeyError, match=r"^'asdf'$"):
        d['asdf'] = 'hello'

@pytest.mark.parametrize(
    argnames=('converter', 'value', 'exp_value'),
    argvalues=(
        (int, 13.5, 13),
        (str, 13.5, '13.5'),
        (lambda value: str(value).split(','), 'a,b,c', ['a', 'b', 'c']),
        (lambda value: [int(v) for v in str(value).split(',')], '1,2,3', [1, 2, 3]),
    ),
    ids=lambda value: str(value),
)
def test_ConfigDict_with_custom_types(converter, value, exp_value):
    d = _ConfigDict(dct={'foo': 2, 'bar': ''}, types={'foo': converter})
    d['foo'] = value
    assert d['foo'] == exp_value
    for v in ('abc', 123, (1, 2, 3)):
        d['bar'] = v
        assert d['bar'] is v

def test_ConfigDict_converter_raises_ValueError():
    dct = {0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}}
    d = _ConfigDict(dct=dct, types={0: {1: int}})
    with pytest.raises(ValueError, match=r"^invalid literal for int\(\) with base 10: 'hello'$"):
        d[0][1] = 'hello'

def test_ConfigDict_converter_raises_TypeError():
    dct = {0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}}
    d = _ConfigDict(dct=dct, types={0: {1: int}})
    with pytest.raises(ValueError, match=r"^int\(\) argument must be a string, a bytes-like object or a number, not 'list'$"):
        d[0][1] = ['hello']

def test_ConfigDict_subdictionaries_are_ConfigDicts():
    d = _ConfigDict({0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}})
    assert isinstance(d[0], _ConfigDict)
    assert isinstance(d[0][3], _ConfigDict)
    assert isinstance(d[0][3][8], _ConfigDict)

def test_ConfigDict_setting_subdictionary_merges_into_current_values():
    dct = {0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}}
    d = _ConfigDict(dct=dct)
    d[0][3] = {6: 600, 8: {9: 1000}}
    assert d == {0: {1: 2, 3: {4: 5, 6: 600, 8: {9: 1000}}}}
    assert isinstance(d[0], _ConfigDict)
    assert isinstance(d[0][3], _ConfigDict)
    assert isinstance(d[0][3][8], _ConfigDict)

def test_ConfigDict_setting_subdictionary_creates_new_subdictionary():
    dct = {0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}}
    d = _ConfigDict(dct=dct)
    del d[0][3]
    d[0][3] = {8: {9: 1000}}
    assert d == {0: {1: 2, 3: {8: {9: 1000}}}}
    assert isinstance(d[0], _ConfigDict)
    assert isinstance(d[0][3], _ConfigDict)
    assert isinstance(d[0][3][8], _ConfigDict)

def test_ConfigDict_setting_subdictionaries_copies_appropriate_subkeys():
    d = _ConfigDict({0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}},
                    keys={0: {1: None, 3: {4: None, 6: None, 8: {9: None}}}})
    assert d[0]._keys == {1: None, 3: {4: None, 6: None, 8: {9: None}}}
    assert d[0][3]._keys == {4: None, 6: None, 8: {9: None}}
    assert d[0][3][8]._keys == {9: None}

def test_ConfigDict_setting_subdictionaries_copies_appropriate_subtypes():
    types = {0: {1: lambda x: None, 3: {4: lambda x: None, 6: lambda x: None, 8: {9: lambda x: None}}}}
    d = _ConfigDict({0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}}, types=types)
    assert d[0]._types is types[0]
    assert d[0][3]._types is types[0][3]
    assert d[0][3][8]._types is types[0][3][8]

def test_ConfigDict_setting_subdictionary_to_nondictionary():
    d = _ConfigDict({0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}})
    with pytest.raises(TypeError, match=r'^Expected dictionary for 8, not int: 100$'):
        d[0][3][8] = 100

def test_ConfigDict_nondictionary_value_to_dictionary():
    d = _ConfigDict({0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}})
    with pytest.raises(TypeError, match=r'^4 is not a dictionary: \{400: 4000\}$'):
        d[0][3][4] = {400: 4000}


def test_init_copies_defaults():
    defaults = {'section': {'subsection1': {'foo': 123, 'bar': 456},
                            'subsection2': {'foo': 789, 'baz': 'xxx'}}}
    config = ConfigFiles(defaults=defaults)
    assert config._defaults == defaults
    assert id(config._defaults) != id(defaults)
    assert id(config._defaults['section']) != id(defaults['section'])
    assert id(config._defaults['section']['subsection1']) != id(defaults['section']['subsection1'])
    assert id(config._defaults['section']['subsection2']) != id(defaults['section']['subsection2'])
    assert config._cfg == config._defaults
    assert isinstance(config._cfg, _ConfigDict)
    assert id(config._cfg) != id(config._defaults)

def test_init_creates_ConfigDict(mocker):
    defaults = {'section': {'subsection1': {'foo': 123, 'bar': 456},
                            'subsection2': {'foo': 789, 'baz': 'xxx'}}}
    ConfigDict_mock = mocker.patch('upsies.utils.configfiles._ConfigDict')
    mocker.patch('upsies.utils.configfiles.ConfigFiles._build_types')
    config = ConfigFiles(defaults=defaults)
    assert config._cfg == ConfigDict_mock.return_value
    assert ConfigDict_mock.call_args_list == [
        call(defaults, types=config._build_types.return_value),
    ]

def test_init_reads_files(mocker):
    mocker.patch('upsies.utils.configfiles.ConfigFiles.read')
    config = ConfigFiles(
        defaults={},
        foo='path/to/foo.ini',
        bar='path/to/bar.ini',
    )
    assert config.read.call_args_list == [
        call('foo', 'path/to/foo.ini'),
        call('bar', 'path/to/bar.ini'),
    ]


def test_build_types():
    class Subclass(str):
        pass

    d = ConfigFiles(defaults={
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], (1, 2, 3): (25, 30.3)}},
        0: {'foo': {'x': ()},
            None: {'x': 123, 'y': 1.23, 'z': Subclass('hello')}},
    })
    types = d._build_types()

    def my_assert(value, exp, type):
        assert value == exp
        assert isinstance(value, type)

    my_assert(types['main']['foo']['a'](1), '1', str)

    my_assert(types['main']['bar']['b']('asdf'), ['asdf'], list)
    my_assert(types['main']['bar']['b']('a s  d\nf and   \n  bar'), ['a', 's', 'd', 'f', 'and', 'bar'], list)
    my_assert(types['main']['bar']['b'](['a', 's', 'd\nf', 'and bar']), ['a', 's', 'd\nf', 'and bar'], list)

    my_assert(types['main']['bar'][(1, 2, 3)](123), ['123'], list)
    my_assert(types['main']['bar'][(1, 2, 3)]((123, 1.23)), [123, 1.23], list)

    my_assert(types[0]['foo']['x'](()), [], list)
    my_assert(types[0]['foo']['x'](('y ', ' z')), ['y ', ' z'], list)
    my_assert(types[0]['foo']['x']('y  z'), ['y', 'z'], list)

    my_assert(types[0][None]['x'](5), 5, int)
    my_assert(types[0][None]['x']('5'), 5, int)

    my_assert(types[0][None]['y'](5), 5.0, float)
    my_assert(types[0][None]['y'](5.3), 5.3, float)
    my_assert(types[0][None]['y']('5.3'), 5.3, float)

    my_assert(types[0][None]['z']('5.3'), '5.3', Subclass)
    my_assert(types[0][None]['z']([5, 3]), '5 3', Subclass)


def test_paths():
    d = ConfigFiles(defaults={
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], (1, 2, 3): 'cee'}},
        0: {'foo': {'x': 'asdf'},
            None: {'y': 'fdsa', 'z': 'qux'}},
    })
    assert d.paths == tuple(sorted((
        'main.foo.a',
        'main.bar.b',
        'main.bar.(1, 2, 3)',
        '0.foo.x',
        '0.None.y',
        '0.None.z',
    )))


def test_setting_unknown_section():
    d = ConfigFiles(defaults={
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], (1, 2, 3): 'cee'}},
        0: {'foo': {'x': 'asdf'},
            None: {'y': 'fdsa', 'z': 'qux'}},
    })
    with pytest.raises(errors.ConfigError, match=r'^nope: Unknown section$'):
        d._set('nope', 'foo', 'a', 'x')

def test_setting_unknown_subsection():
    d = ConfigFiles(defaults={
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], (1, 2, 3): 'cee'}},
        0: {'foo': {'x': 'asdf'},
            None: {'y': 'fdsa', 'z': 'qux'}},
    })
    with pytest.raises(errors.ConfigError, match=r'^main\.nope: Unknown subsection$'):
        d._set('main', 'nope', 'a', 'x')

def test_setting_unknown_option():
    d = ConfigFiles(defaults={
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], (1, 2, 3): 'cee'}},
        0: {'foo': {'x': 'asdf'},
            None: {'y': 'fdsa', 'z': 'qux'}},
    })
    with pytest.raises(errors.ConfigError, match=r'^main\.foo\.nope: Unknown option$'):
        d._set('main', 'foo', 'nope', 'x')

def test_setting_option_to_invalid_value():
    d = ConfigFiles(defaults={
        'main': {'foo': {'a': 123},
                 'bar': {'b': ['x'], (1, 2, 3): 'cee'}},
        0: {'foo': {'x': 'asdf'},
            None: {'y': 'fdsa', 'z': 'qux'}},
    })
    with pytest.raises(errors.ConfigError, match=r"^main\.foo\.a: invalid literal for int\(\) with base 10: 'not a number'$"):
        d._set('main', 'foo', 'a', 'not a number')
    assert d['main.foo.a'] == 123


@patch('upsies.utils.configfiles._path_exists')
def test_read_ignores_nonexisting_path(path_exists_mock):
    path_exists_mock.return_value = False
    config = ConfigFiles(defaults={})
    config.read('foo', 'path/to/no/such/file.ini', ignore_missing=True)
    assert config._cfg == {}
    assert config._files == {'foo': 'path/to/no/such/file.ini'}

@patch('upsies.utils.configfiles._path_exists')
def test_read_does_not_ignore_nonexisting_path(path_exists_mock):
    path_exists_mock.return_value = False
    config = ConfigFiles(defaults={})
    with pytest.raises(errors.ConfigError, match=r'^path/to/no/such/file.ini: No such file or directory$'):
        config.read('foo', 'path/to/no/such/file.ini', ignore_missing=False)
    assert config._cfg == {}
    assert config._files == {}

@pytest.mark.parametrize('ignore_missing', (True, False), ids=lambda v: f'ignore_missing={v!r}')
def test_read_fails_to_read_file(ignore_missing, tmp_path):
    filepath = tmp_path / 'file.ini'
    filepath.write_text('abc')
    filepath.chmod(0o000)
    try:
        config = ConfigFiles(defaults={})
        with pytest.raises(errors.ConfigError, match=rf'^{filepath}: Permission denied$'):
            config.read('foo', filepath, ignore_missing=ignore_missing)
        assert config._cfg == {}
        assert config._files == {}
    finally:
        filepath.chmod(0o660)

@pytest.mark.parametrize('ignore_missing', (True, False), ids=lambda v: f'ignore_missing={v!r}')
def test_read_updates_values(ignore_missing, tmp_path, mocker):
    defaults = {
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], 'c': 'x'}},
        'other': {'foo': {'x': 'asdf'},
                  'baz': {'y': 'fdsa', 'z': 'qux'}},
    }
    file_main = tmp_path / 'file_main.ini'
    file_main.write_text('[bar]\nc = cee\n\n[foo]\na = z\n')
    file_other = tmp_path / 'file_other.ini'
    file_other.write_text('[foo]\nx = hello\n\n[baz]\ny = world\n')

    mocker.patch('upsies.utils.configfiles.ConfigFiles._set')
    config = ConfigFiles(defaults=defaults)

    assert config.read('main', file_main, ignore_missing=ignore_missing) is None
    assert config._set.call_args_list == [
        call('main', 'bar', 'c', 'cee'),
        call('main', 'foo', 'a', 'z'),
    ]
    assert config._files == {'main': file_main}
    assert config._defaults == defaults

    config._set.reset_mock()
    assert config.read('other', file_other, ignore_missing=ignore_missing) is None
    assert config._set.call_args_list == [
        call('other', 'foo', 'x', 'hello'),
        call('other', 'baz', 'y', 'world'),
    ]
    assert config._files == {'main': file_main, 'other': file_other}
    assert config._defaults == defaults


def test_parse_option_outside_of_section():
    with pytest.raises(errors.ConfigError, match=r"^mock/path.ini: Line 1: foo = bar: Option outside of section$"):
        ConfigFiles._parse('section1', 'foo = bar\n', 'mock/path.ini')

def test_parse_finds_invalid_syntax():
    with pytest.raises(errors.ConfigError, match=r"^mock/path.ini: Line 2: 'foo\\n': Invalid syntax$"):
        ConfigFiles._parse('section1', '[section]\nfoo\n', 'mock/path.ini')

def test_parse_finds_duplicate_section():
    config = ConfigFiles(defaults={})
    with pytest.raises(errors.ConfigError, match=r'^mock/path.ini: Line 3: asdf: Duplicate section$'):
        config._parse('section1', '[asdf]\nfoo = bar\n[asdf]\na = b\n', 'mock/path.ini')

def test_parse_finds_duplicate_option():
    with pytest.raises(errors.ConfigError, match=r'^mock/path.ini: Line 3: foo: Duplicate option$'):
        ConfigFiles._parse('section1', '[section]\nfoo = bar\nfoo = baz\n', 'mock/path.ini')

@patch('configparser.ConfigParser')
def test_parse_catches_generic_error(ConfigParser_mock):
    ConfigParser_mock.return_value.read_string.side_effect = configparser.Error('Something')
    with pytest.raises(errors.ConfigError, match=r"^mock/path.ini: Something$"):
        ConfigFiles._parse('section1', '', 'mock/path.ini')

def test_parse_returns_nested_dictionary():
    cfg = ConfigFiles._parse('section1', '[foo]\na = 1\nb = 2\n[bar]\n1 = one\n', 'mock/path.ini')
    assert cfg == {'foo': {'a': '1',
                           'b': '2'},
                   'bar': {'1': 'one'}}

def test_parse_uses_newlines_as_list_separator():
    cfg = ConfigFiles._parse('section1', '[foo]\na = 1\n 2\n    3\n', 'mock/path.ini')
    assert cfg == {'foo': {'a': ['1', '2', '3']}}


def test_get_nonstring_key():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    with pytest.raises(KeyError, match=r"^\(1, 2, 3\)$"):
        config[(1, 2, 3)]

def test_get_section():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config._set('foo', 'bar', 'qux', 456)
    config._set('hey', 'you', 'up', '!')
    section = config['foo']
    assert section == {'bar': {'baz': 'asdf', 'qux': 456}}
    assert isinstance(section, _ConfigDict)
    section = config['hey']
    assert section == {'you': {'there': 'whats', 'up': '!'}}
    assert isinstance(section, _ConfigDict)

def test_get_unknown_section():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['nope']

def test_get_subsection():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config._set('foo', 'bar', 'qux', 456)
    config._set('hey', 'you', 'up', '!')
    subsection = config['foo']['bar']
    assert subsection == {'baz': 'asdf', 'qux': 456}
    assert isinstance(subsection, _ConfigDict)
    subsection = config['hey']['you']
    assert subsection == {'there': 'whats', 'up': '!'}
    assert isinstance(subsection, _ConfigDict)

def test_get_subsection_with_dot_notation():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config._set('foo', 'bar', 'qux', 456)
    config._set('hey', 'you', 'up', '!')
    subsection = config['foo.bar']
    assert subsection == {'baz': 'asdf', 'qux': 456}
    assert isinstance(subsection, _ConfigDict)
    subsection = config['hey.you']
    assert subsection == {'there': 'whats', 'up': '!'}
    assert isinstance(subsection, _ConfigDict)

def test_get_unknown_subsection():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo']['nope']

def test_get_unknown_subsection_with_dot_notation():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo.nope']

def test_get_option():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config._set('foo', 'bar', 'qux', 456)
    config._set('hey', 'you', 'up', '!')
    assert config['foo']['bar']['baz'] == 'asdf'
    assert config['foo']['bar']['qux'] == 456
    assert config['hey']['you']['there'] == 'whats'
    assert config['hey']['you']['up'] == '!'

def test_get_option_with_dot_notation():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config._set('foo', 'bar', 'qux', 456)
    config._set('hey', 'you', 'up', '!')
    assert config['foo.bar.baz'] == 'asdf'
    assert config['foo.bar.qux'] == 456
    assert config['hey.you.there'] == 'whats'
    assert config['hey.you.up'] == '!'

def test_get_unknown_option():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo']['bar']['nope']

def test_get_unknown_option_with_dot_notation():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo.bar.nope']


def test_set_nonstring_section():
    config = ConfigFiles(defaults={(1, 2, 3): {'bar': {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config[(1, 2, 3)]['bar']['baz'] = 'not asdf'
    assert config[(1, 2, 3)] == {'bar': {'baz': 'not asdf', 'qux': 123}}

def test_set_nonstring_subsection():
    config = ConfigFiles(defaults={'foo': {(1, 2, 3): {'baz': 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config['foo'][(1, 2, 3)]['baz'] = 'not asdf'
    assert config['foo'] == {(1, 2, 3): {'baz': 'not asdf', 'qux': 123}}

def test_set_nonstring_option():
    config = ConfigFiles(defaults={'foo': {'bar': {(1, 2, 3): 'asdf', 'qux': 123}},
                                   'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config['foo']['bar'][(1, 2, 3)] = 'not asdf'
    assert config['foo'] == {'bar': {(1, 2, 3): 'not asdf', 'qux': 123}}

def test_set_valid_section():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    config['foo'] = {'bar': {'baz': 'hello', 'qux': 456}}
    assert config['foo'] == {'bar': {'baz': 'hello', 'qux': 456, 'asdf': [1, 2, 3]}}

def test_set_valid_subsection():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    config['foo']['bar'] = {'baz': 'hello', 'qux': 456}
    assert config['foo'] == {'bar': {'baz': 'hello', 'qux': 456, 'asdf': [1, 2, 3]}}

def test_set_valid_option():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    config['foo']['bar']['baz'] = 'hello'
    assert config['foo'] == {'bar': {'baz': 'hello', 'qux': 123, 'asdf': [1, 2, 3]}}

def test_set_invalid_section():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    with pytest.raises(TypeError, match=r"^Expected dictionary for foo, not str: 'asdf'$"):
        config['foo'] = 'asdf'
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}

def test_set_invalid_subsection():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    with pytest.raises(TypeError, match=r"^Expected dictionary for bar, not str: 'asdf'$"):
        config['foo']['bar'] = 'asdf'
    with pytest.raises(TypeError, match=r"^Expected dictionary for bar, not str: 'asdf'$"):
        config['foo.bar'] = 'asdf'
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}

def test_set_converts_option_to_list_if_applicable():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    config['foo']['bar']['asdf'] = 'not a list'
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': ['not', 'a', 'list']}}
    config['foo.bar.asdf'] = 'also not a list'
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': ['also', 'not', 'a', 'list']}}

def test_set_unknown_section():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['nope'] = {'bar': {'baz': 'asdf'}}
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}

def test_set_unknown_subsection():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo']['nope'] = {'baz': 'asdf'}
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo.nope'] = {'baz': 'asdf'}
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}

def test_set_unknown_option():
    config = ConfigFiles(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo']['bar']['nope'] = 'hello'
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo.bar.nope'] = 'hello'
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}


def test_iterating_over_ConfigFiles():
    config = ConfigFiles(defaults={
        'foo': {
            'bar': {'baz': 'asdf'},
            'this': {'that': 'arf'},
        },
        'hey': {
            'you': {'there': ''},
        },
    })
    assert tuple(config) == ('foo', 'hey')


@pytest.mark.parametrize(
    argnames=('args', 'exp_args'),
    argvalues=(
        ((), ('', '', '')),
        (('foo',), ('foo', '', '')),
        (('foo.bar',), ('foo', 'bar', '')),
        (('foo.bar.baz',), ('foo', 'bar', 'baz')),
    ),
    ids=lambda value: str(value),
)
def test_reset_calls_private_reset_method(args, exp_args, mocker):
    mocker.patch('upsies.utils.configfiles.ConfigFiles._reset')
    config = ConfigFiles(defaults={})
    config.reset(*args)
    assert config._reset.call_args_list == [call(*exp_args)]


def test__reset_everything():
    config = ConfigFiles(defaults={
        'foo': {
            'bar': {'baz': 'asdf', 'qux': 123},
            'this': {'that': 'arf', 'qux': 456},
        },
        'hey': {
            'you': {'there': 'whats', 'up': '?'},
        },
    })
    config['foo.bar.baz'] = 'changed'
    config['foo.this.qux'] = 789
    config['hey.you.there'] = 'changed'
    config._reset()
    assert config._cfg == config._defaults

def test__reset_section():
    config = ConfigFiles(defaults={
        'foo': {
            'bar': {'baz': 'asdf', 'qux': 123},
            'this': {'that': 'arf', 'qux': 456},
        },
        'hey': {
            'you': {'there': 'whats', 'up': '?'},
        },
    })
    config['foo.bar.baz'] = 'changed'
    config['foo.this.qux'] = 789
    config['hey.you.there'] = 'changed'
    config._reset('foo')
    assert config._cfg == {
        'foo': {
            'bar': {'baz': 'asdf', 'qux': 123},
            'this': {'that': 'arf', 'qux': 456},
        },
        'hey': {
            'you': {'there': 'changed', 'up': '?'},
        },
    }

def test__reset_subsection():
    config = ConfigFiles(defaults={
        'foo': {
            'bar': {'baz': 'asdf', 'qux': 123},
            'this': {'that': 'arf', 'qux': 456},
        },
        'hey': {
            'you': {'there': 'whats', 'up': '?'},
        },
    })
    config['foo.bar.baz'] = 'changed'
    config['foo.this.qux'] = 789
    config['hey.you.there'] = 'changed'
    config._reset('foo', 'this')
    assert config._cfg == {
        'foo': {
            'bar': {'baz': 'changed', 'qux': 123},
            'this': {'that': 'arf', 'qux': 456},
        },
        'hey': {
            'you': {'there': 'changed', 'up': '?'},
        },
    }

def test__reset_option():
    config = ConfigFiles(defaults={
        'foo': {
            'bar': {'baz': 'asdf', 'qux': 123},
            'this': {'that': 'arf', 'qux': 456},
        },
        'hey': {
            'you': {'there': 'whats', 'up': '?'},
        },
    })
    config['foo.bar.baz'] = 'changed'
    config['foo.this.that'] = 'arf and arf'
    config['foo.this.qux'] = 789
    config['hey.you.there'] = 'changed'
    config._reset('foo', 'this', 'qux')
    assert config._cfg == {
        'foo': {
            'bar': {'baz': 'changed', 'qux': 123},
            'this': {'that': 'arf and arf', 'qux': 456},
        },
        'hey': {
            'you': {'there': 'changed', 'up': '?'},
        },
    }


@pytest.mark.parametrize(
    argnames='args',
    argvalues=(
        (),
        ('File_1',),
        ('File_2',),
        ('File_1', 'File_2'),
        ('File_1.foo', 'File_2.foo.bar'),
    ),
    ids=lambda v: str(v),
)
def test_write_writes_given_files(args, tmp_path):
    file1 = tmp_path / 'file1.ini'
    file2 = tmp_path / 'file2.ini'
    file1.write_text('[foo]\nbar = baz\n')
    file2.write_text('[foo]\nbar = baz\n')
    config = ConfigFiles(
        defaults={
            'File_1': {'foo': {'bar': 'qux'}},
            'File_2': {'foo': {'bar': 'qux'}},
        },
        File_1=file1,
        File_2=file2,
    )
    config['File_1.foo.bar'] = 'config written'
    config['File_2.foo.bar'] = 'config written'
    config.write(*args)
    if not args:
        files_changed = (file1, file2)
    else:
        files_changed = []
        if any(arg.startswith('File_1') for arg in args):
            files_changed.append(file1)
        if any(arg.startswith('File_2') for arg in args):
            files_changed.append(file2)
    for f in files_changed:
        assert open(f).read() == '[foo]\nbar = config written\n'

@pytest.mark.parametrize(argnames='arg', argvalues=('main', 'main.foo'))
def test_write_extracts_section_from_argument(arg, tmp_path):
    file = tmp_path / 'file1.ini'
    file.write_text('[foo]\nbar = baz\n')
    config = ConfigFiles(
        defaults={
            'main': {'foo': {'bar': 'qux'}},
        },
        main=file,
    )
    config['main.foo.bar'] = 'config written'
    config.write(arg)
    assert open(file).read() == '[foo]\nbar = config written\n'

def test_write_fails_to_write_file(tmp_path):
    file = tmp_path / 'file1.ini'
    file.write_text('[foo]\nbar = baz\n')
    config = ConfigFiles(
        defaults={'main': {'foo': {'bar': 'qux'}}},
        main=file,
    )
    os.chmod(file, 0o000)
    try:
        with pytest.raises(errors.ConfigError, match=rf'^{file}: Permission denied$'):
            config.write('main')
    finally:
        os.chmod(file, 0o600)


def test_as_ini():
    config = ConfigFiles(
        defaults={'main': {
            'foo': {'a': 'aaa', 'b': [1, 2, 3], 'c': 123},
            'bar': {'b': 'bbb', 'c': [4, 5, 6], 'd': 456},
            'baz': {'c': 'ccc', 'd': [7, 8, 9], 'e': 789},
        }},
    )
    config['main.foo.a'] = 'AAA'
    config['main.bar.c'] = [100, 200, 300]
    config['main.baz.d'] = []
    config['main.baz.e'] = 1000
    exp_ini_string = (
        '[foo]\n'
        'a = AAA\n'
        '\n'
        '[bar]\n'
        'c =\n'
        '  100\n'
        '  200\n'
        '  300\n'
        '\n'
        '[baz]\n'
        'd =\n'
        'e = 1000\n'
    )
    assert config._as_ini('main') == exp_ini_string
