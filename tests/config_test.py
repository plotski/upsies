import collections
import configparser
import os
from unittest.mock import call, patch

import pytest

from upsies import errors
from upsies.config import Config
from upsies.config._config import _SpecDict


def test_SpecDict_is_dict_instance():
    d = _SpecDict(
        spec={'foo': 'bar'},
        dct={'foo': 'baz'},
    )
    assert isinstance(d, dict)

def test_SpecDict_implements_delitem():
    d = _SpecDict(
        spec={'foo': 'bar', 'bar': 'abc'},
        dct={'foo': 'baz', 'bar': 'xyz'},
    )
    del d['bar']
    assert d == {'foo': 'baz'}

def test_SpecDict_implements_len():
    d = _SpecDict(
        spec={'foo': 'bar', 'bar': 'abc'},
        dct={'foo': 'baz', 'bar': 'xyz'},
    )
    assert len(d) == 2

def test_SpecDict_implements_repr():
    d = _SpecDict(
        spec={'foo': 'bar', 'bar': 'abc'},
        dct={'foo': 'baz', 'bar': 'xyz'},
    )
    assert repr(d) == repr({'foo': 'baz', 'bar': 'xyz'})

def test_SpecDict_raises_KeyError_when_setting_unknown_key():
    d = _SpecDict(
        spec={'foo': 'bar'},
        dct={'foo': 'baz'},
    )
    with pytest.raises(KeyError, match=r"^'asdf'$"):
        d['asdf'] = 'hello'

def test_SpecDict_raises_TypeError_when_setting_wrong_type():
    d = _SpecDict(
        spec={'foo': [1, 2, 3]},
        dct={'foo': [2, 3, 4]},
    )
    with pytest.raises(TypeError, match=r'^Expected list for foo, not int: 345$'):
        d['foo'] = 345

def test_SpecDict_accepts_correct_type():
    d = _SpecDict(
        spec={'foo': [1, 2, 3]},
        dct={'foo': [2, 3, 4]},
    )
    d['foo'] = [3, 4, 5]
    assert d['foo'] == [3, 4, 5]

@pytest.mark.parametrize(
    argnames=('value', 'exp_value'),
    argvalues=(
        (13, 26),
        (13.35, 26.7),
        ([3, 4, 5], '3:4:5'),
        ((3, 4, 5), '3:4:5'),
        (iter((3, 4, 5)), '3::4::5'),
        (NotImplemented, '[NotImplemented]'),
    ),
    ids=lambda value: str(value),
)
def test_SpecDict_converts_with_converter(value, exp_value):
    d = _SpecDict(
        spec={'foo': '1'},
        dct={'foo': '2'},
        converters={
            (int, float): lambda value: value * 2,
            collections.abc.Sequence: lambda value: ':'.join(str(v) for v in value),
            (collections.abc.Iterable,): lambda value: '::'.join(str(v) for v in value),
            None: lambda value: f'[{value}]',
        },
    )
    d['foo'] = value
    assert d['foo'] == exp_value

def test_SpecDict_subdictionaries_are_SpecDicts():
    dct = {0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}}
    d = _SpecDict(spec=dct, dct=dct)
    assert isinstance(d[0], _SpecDict)
    assert isinstance(d[0][3], _SpecDict)
    assert isinstance(d[0][3][8], _SpecDict)

def test_SpecDict_setting_subdictionary_to_nondictionary():
    dct = {0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}}
    d = _SpecDict(spec=dct, dct=dct)
    with pytest.raises(TypeError, match=r'^Expected dict for 8, not int: 100$'):
        d[0][3][8] = 100

def test_SpecDict_nondictionary_value_to_dictionary():
    dct = {0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}}
    d = _SpecDict(spec=dct, dct=dct)
    with pytest.raises(TypeError, match=r'^Expected int for 4, not dict: \{400: 4000\}$'):
        d[0][3][4] = {400: 4000}

def test_SpecDict_setting_subdictionary_merges():
    dct = {0: {1: 2, 3: {4: 5, 6: 7, 8: {9: 0}}}}
    d = _SpecDict(spec=dct, dct=dct)
    d[0][3] = {6: 600, 8: {9: 1000}}
    assert d == {0: {1: 2, 3: {4: 5, 6: 600, 8: {9: 1000}}}}


def test_init_copies_defaults():
    defaults = {'section': {'subsection1': {'foo': 123, 'bar': 456},
                            'subsection2': {'foo': 789, 'baz': 'xxx'}}}
    config = Config(defaults=defaults)
    assert config._defaults == defaults
    assert id(config._defaults) != id(defaults)
    assert id(config._defaults['section']) != id(defaults['section'])
    assert id(config._defaults['section']['subsection1']) != id(defaults['section']['subsection1'])
    assert id(config._defaults['section']['subsection2']) != id(defaults['section']['subsection2'])
    assert config._cfg == config._defaults
    assert isinstance(config._cfg, _SpecDict)
    assert id(config._cfg) != id(config._defaults)

def test_init_reads_files(mocker):
    mocker.patch('upsies.config.Config.read')
    config = Config(
        defaults={},
        foo='path/to/foo.ini',
        bar='path/to/bar.ini',
    )
    assert config.read.call_args_list == [
        call('foo', 'path/to/foo.ini'),
        call('bar', 'path/to/bar.ini'),
    ]


@patch('upsies.config._config._path_exists')
def test_read_ignores_nonexisting_path(path_exists_mock):
    path_exists_mock.return_value = False
    config = Config(defaults={})
    config.read('foo', 'path/to/no/such/file.ini', ignore_missing=True)
    assert config._cfg == {}
    assert config._files == {'foo': 'path/to/no/such/file.ini'}

@patch('upsies.config._config._path_exists')
def test_read_does_not_ignore_nonexisting_path(path_exists_mock):
    path_exists_mock.return_value = False
    config = Config(defaults={})
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
        config = Config(defaults={})
        with pytest.raises(errors.ConfigError, match=rf'^{filepath}: Permission denied$'):
            config.read('foo', filepath, ignore_missing=ignore_missing)
        assert config._cfg == {}
        assert config._files == {}
    finally:
        filepath.chmod(0o660)

@pytest.mark.parametrize('ignore_missing', (True, False), ids=lambda v: f'ignore_missing={v!r}')
def test_read_unknown_section(ignore_missing, tmp_path):
    defaults = {
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], 'c': 'x'}},
    }
    file_main = tmp_path / 'file_main.ini'
    file_main.write_text('[bar]\nc = cee\n\n[foo]\n')
    config = Config(defaults=defaults)
    with pytest.raises(errors.ConfigError, match=rf'{file_main}: nope: Unknown section'):
        assert config.read('nope', file_main, ignore_missing=ignore_missing) is None
    assert config._cfg == {
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], 'c': 'x'}},
    }
    assert config._files == {}
    assert config._defaults == defaults

@pytest.mark.parametrize('ignore_missing', (True, False), ids=lambda v: f'ignore_missing={v!r}')
def test_read_unknown_subsection(ignore_missing, tmp_path):
    defaults = {
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], 'c': 'x'}},
    }
    file_main = tmp_path / 'file_main.ini'
    file_main.write_text('[nope]\nc = cee\n')
    config = Config(defaults=defaults)
    with pytest.raises(errors.ConfigError, match=rf'{file_main}: main.nope: Unknown subsection'):
        assert config.read('main', file_main, ignore_missing=ignore_missing) is None
    assert config._cfg == {
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], 'c': 'x'}},
    }
    assert config._files == {}
    assert config._defaults == defaults

@pytest.mark.parametrize('ignore_missing', (True, False), ids=lambda v: f'ignore_missing={v!r}')
def test_read_unknown_option(ignore_missing, tmp_path):
    defaults = {
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], 'c': 'x'}},
    }
    file_main = tmp_path / 'file_main.ini'
    file_main.write_text('[bar]\nnope = dope\n')
    config = Config(defaults=defaults)
    with pytest.raises(errors.ConfigError, match=rf'{file_main}: main.bar.nope: Unknown option'):
        assert config.read('main', file_main, ignore_missing=ignore_missing) is None
    assert config._cfg == {
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], 'c': 'x'}},
    }
    assert config._files == {}
    assert config._defaults == defaults

@pytest.mark.parametrize('ignore_missing', (True, False), ids=lambda v: f'ignore_missing={v!r}')
def test_read_updates_values(ignore_missing, tmp_path):
    defaults = {
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], 'c': 'x'}},
        'other': {'foo': {'x': 'asdf'},
                  'baz': {'y': 'fdsa', 'z': 'qux'}},
    }
    file_main = tmp_path / 'file_main.ini'
    file_main.write_text('[bar]\nc = cee\n\n[foo]\n')
    file_other = tmp_path / 'file_other.ini'
    file_other.write_text('[foo]\nx = hello\n\n[baz]\ny = world\n')
    config = Config(defaults=defaults)

    assert config.read('main', file_main, ignore_missing=ignore_missing) is None
    assert config._cfg == {
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], 'c': 'cee'}},
        'other': {'foo': {'x': 'asdf'},
                  'baz': {'y': 'fdsa', 'z': 'qux'}},
    }
    assert config._files == {'main': file_main}
    assert config._defaults == defaults

    assert config.read('other', file_other, ignore_missing=ignore_missing) is None
    assert config._cfg == {
        'main': {'foo': {'a': 'x'},
                 'bar': {'b': ['x'], 'c': 'cee'}},
        'other': {'foo': {'x': 'hello'},
                  'baz': {'y': 'world', 'z': 'qux'}},
    }
    assert config._files == {'main': file_main, 'other': file_other}
    assert config._defaults == defaults


def test_parse_option_outside_of_section():
    with pytest.raises(errors.ConfigError, match=r"^mock/path.ini: Line 1: foo = bar: Option outside of section$"):
        Config._parse('section1', 'foo = bar\n', 'mock/path.ini')

def test_parse_finds_invalid_syntax():
    with pytest.raises(errors.ConfigError, match=r"^mock/path.ini: Line 2: 'foo\\n': Invalid syntax$"):
        Config._parse('section1', '[section]\nfoo\n', 'mock/path.ini')

def test_parse_finds_duplicate_section():
    config = Config(defaults={})
    with pytest.raises(errors.ConfigError, match=r'^mock/path.ini: Line 3: asdf: Duplicate section$'):
        config._parse('section1', '[asdf]\nfoo = bar\n[asdf]\na = b\n', 'mock/path.ini')

def test_parse_finds_duplicate_option():
    with pytest.raises(errors.ConfigError, match=r'^mock/path.ini: Line 3: foo: Duplicate option$'):
        Config._parse('section1', '[section]\nfoo = bar\nfoo = baz\n', 'mock/path.ini')

@patch('configparser.ConfigParser')
def test_parse_catches_generic_error(ConfigParser_mock):
    ConfigParser_mock.return_value.read_string.side_effect = configparser.Error('Something')
    with pytest.raises(errors.ConfigError, match=r"^mock/path.ini: Something$"):
        Config._parse('section1', '', 'mock/path.ini')

def test_parse_returns_nested_dictionary():
    cfg = Config._parse('section1', '[foo]\na = 1\nb = 2\n[bar]\n1 = one\n', 'mock/path.ini')
    assert cfg == {'foo': {'a': '1',
                           'b': '2'},
                   'bar': {'1': 'one'}}

def test_parse_uses_newlines_as_list_separator():
    cfg = Config._parse('section1', '[foo]\na = 1\n 2\n    3\n', 'mock/path.ini')
    assert cfg == {'foo': {'a': ['1', '2', '3']}}


def test_get_section():
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                              'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config._set('foo', 'bar', 'qux', 456)
    config._set('hey', 'you', 'up', '!')
    section = config['foo']
    assert section == {'bar': {'baz': 'asdf', 'qux': 456}}
    assert isinstance(section, _SpecDict)
    section = config['hey']
    assert section == {'you': {'there': 'whats', 'up': '!'}}
    assert isinstance(section, _SpecDict)

def test_get_unknown_section():
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                              'hey': {'you': {'there': 'whats', 'up': '?'}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['nope']

def test_get_subsection():
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                              'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config._set('foo', 'bar', 'qux', 456)
    config._set('hey', 'you', 'up', '!')
    subsection = config['foo']['bar']
    assert subsection == {'baz': 'asdf', 'qux': 456}
    assert isinstance(subsection, _SpecDict)
    subsection = config['hey']['you']
    assert subsection == {'there': 'whats', 'up': '!'}
    assert isinstance(subsection, _SpecDict)

def test_get_subsection_with_dot_notation():
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                              'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config._set('foo', 'bar', 'qux', 456)
    config._set('hey', 'you', 'up', '!')
    subsection = config['foo.bar']
    assert subsection == {'baz': 'asdf', 'qux': 456}
    assert isinstance(subsection, _SpecDict)
    subsection = config['hey.you']
    assert subsection == {'there': 'whats', 'up': '!'}
    assert isinstance(subsection, _SpecDict)

def test_get_unknown_subsection():
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                              'hey': {'you': {'there': 'whats', 'up': '?'}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo']['nope']

def test_get_unknown_subsection_with_dot_notation():
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                              'hey': {'you': {'there': 'whats', 'up': '?'}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo.nope']

def test_get_option():
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                              'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config._set('foo', 'bar', 'qux', 456)
    config._set('hey', 'you', 'up', '!')
    assert config['foo']['bar']['baz'] == 'asdf'
    assert config['foo']['bar']['qux'] == 456
    assert config['hey']['you']['there'] == 'whats'
    assert config['hey']['you']['up'] == '!'

def test_get_option_with_dot_notation():
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                              'hey': {'you': {'there': 'whats', 'up': '?'}}})
    config._set('foo', 'bar', 'qux', 456)
    config._set('hey', 'you', 'up', '!')
    assert config['foo.bar.baz'] == 'asdf'
    assert config['foo.bar.qux'] == 456
    assert config['hey.you.there'] == 'whats'
    assert config['hey.you.up'] == '!'

def test_get_unknown_option():
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                              'hey': {'you': {'there': 'whats', 'up': '?'}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo']['bar']['nope']

def test_get_unknown_option_with_dot_notation():
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123}},
                              'hey': {'you': {'there': 'whats', 'up': '?'}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo.bar.nope']


def test_set_valid_section(mocker):
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    config['foo'] = {'bar': {'baz': 'hello', 'qux': 456}}
    assert config['foo'] == {'bar': {'baz': 'hello', 'qux': 456, 'asdf': [1, 2, 3]}}

def test_set_valid_subsection(mocker):
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    config['foo']['bar'] = {'baz': 'hello', 'qux': 456}
    assert config['foo'] == {'bar': {'baz': 'hello', 'qux': 456, 'asdf': [1, 2, 3]}}

def test_set_valid_option(mocker):
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    config['foo']['bar']['baz'] = 'hello'
    assert config['foo'] == {'bar': {'baz': 'hello', 'qux': 123, 'asdf': [1, 2, 3]}}

def test_set_invalid_section(mocker):
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    with pytest.raises(TypeError, match=r"^Expected dict for foo, not str: 'asdf'$"):
        config['foo'] = 'asdf'
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}

def test_set_invalid_subsection(mocker):
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    with pytest.raises(TypeError, match=r"^Expected dict for bar, not str: 'asdf'$"):
        config['foo']['bar'] = 'asdf'
    with pytest.raises(TypeError, match=r"^Expected dict for bar, not str: 'asdf'$"):
        config['foo.bar'] = 'asdf'
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}

def test_set_converts_option_to_list_if_applicable(mocker):
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    config['foo']['bar']['asdf'] = 'not a list'
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': ['not', 'a', 'list']}}
    config['foo.bar.asdf'] = 'also not a list'
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': ['also', 'not', 'a', 'list']}}

def test_set_unknown_section(mocker):
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['nope'] = {'bar': {'baz': 'asdf'}}
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}

def test_set_unknown_subsection(mocker):
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo']['nope'] = {'baz': 'asdf'}
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo.nope'] = {'baz': 'asdf'}
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}

def test_set_unknown_option(mocker):
    config = Config(defaults={'foo': {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}})
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo']['bar']['nope'] = 'hello'
    with pytest.raises(KeyError, match=r"^'nope'$"):
        config['foo.bar.nope'] = 'hello'
    assert config['foo'] == {'bar': {'baz': 'asdf', 'qux': 123, 'asdf': [1, 2, 3]}}


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
    config = Config(
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
    config = Config(
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
    config = Config(
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
    config = Config(
        defaults={'main': {
            'foo': {'a': 'aaa', 'b': [1, 2, 3], 'c': 123},
            'bar': {'b': 'bbb', 'c': [], 'd': 456},
        }},
    )
    exp_ini_string = (
        '[foo]\n'
        'a = aaa\n'
        'b =\n'
        '  1\n'
        '  2\n'
        '  3\n'
        'c = 123\n'
        '\n'
        '[bar]\n'
        'b = bbb\n'
        'c =\n'
        'd = 456\n'
    )
    assert config._as_ini('main') == exp_ini_string
