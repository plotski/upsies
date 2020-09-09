from unittest.mock import patch, call

import pytest

from upsies import errors
from upsies.config import Config


def test_apply_defaults_gets_empty_config():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    assert config._apply_defaults('section1', {}) == config._defaults['section1']
    assert config._apply_defaults('section2', {}) == config._defaults['section2']

def test_apply_defaults_fills_in_empty_section():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    cfg = {'subsection1': {'a': '100', 'b': '200', 'c': '300'}}
    assert config._apply_defaults('section1', cfg) == {'subsection1': {'a': '100', 'b': '200', 'c': '300'},
                                                       'subsection2': {'b': '4', 'c': '5', 'd': '6'}}
    cfg = {'subsection2': {'b': '400', 'c': '500', 'd': '600'}}
    assert config._apply_defaults('section1', cfg) == {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                                       'subsection2': {'b': '400', 'c': '500', 'd': '600'}}
    cfg = {'subsection2': {'x': '10.5', 'y': '20.5', 'z': '30.5'}}
    assert config._apply_defaults('section2', cfg) == {'subsection2': {'x': '10.5', 'y': '20.5', 'z': '30.5'},
                                                       'subsection3': {'y': '40', 'z': '50', '_': '60'}}
    cfg = {'subsection3': {'y': '40.5', 'z': '50.5', '_': '60.5'}}
    assert config._apply_defaults('section2', cfg) == {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                                       'subsection3': {'y': '40.5', 'z': '50.5', '_': '60.5'}}

def test_apply_defaults_fills_in_missing_options():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    cfg = {'subsection1': {'a': '100', 'c': '300'},
           'subsection2': {'b': '40', 'c': '50'}}
    assert config._apply_defaults('section1', cfg) == {'subsection1': {'a': '100', 'b': '2', 'c': '300'},
                                                       'subsection2': {'b': '40', 'c': '50', 'd': '6'}}
    cfg = {'subsection1': {},
           'subsection2': {'b': '40', 'c': '50'},}
    assert config._apply_defaults('section1', cfg) == {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                                       'subsection2': {'b': '40', 'c': '50', 'd': '6'}}


def test_validate_finds_unknown_section():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    with pytest.raises(errors.ConfigError, match=r'^Unknown section: section5$'):
        config._validate('section5', {'foo': 'bar'}, 'path/to/section1.ini')

def test_validate_finds_unknown_subsection():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    with pytest.raises(errors.ConfigError, match=r'^path/to/section1.ini: Unknown section: foo$'):
        config._validate('section1', {'foo': {'bar': 'baz'}}, 'path/to/section1.ini')

def test_validate_finds_unknown_option():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    with pytest.raises(errors.ConfigError, match=r'^path/to/section1.ini: subsection2: Unknown option: bar$'):
        config._validate('section1', {'subsection2': {'bar': 'baz'}}, 'path/to/section1.ini')

def test_validate_returns_valid_config():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    cfg = {'subsection2': {'b': '0'}}
    assert config._validate('section1', cfg, 'path/to/section1.ini') == cfg


def test_parse_finds_duplicate_section():
    config = Config(defaults={})
    with pytest.raises(errors.ConfigError, match=r'^mock/path.ini: Line 3: Duplicate section: asdf$'):
        config._parse('section1', '[asdf]\nfoo = bar\n[asdf]\na = b\n', 'mock/path.ini')

def test_parse_finds_duplicate_option():
    config = Config(defaults={})
    with pytest.raises(errors.ConfigError, match=r'^mock/path.ini: Line 3: Duplicate option: foo$'):
        config._parse('section1', '[section]\nfoo = bar\nfoo = baz\n', 'mock/path.ini')

def test_parse_finds_invalid_syntax():
    config = Config(defaults={})
    with pytest.raises(errors.ConfigError, match=r"^mock/path.ini: Line 2: Invalid syntax: 'foo\\n'$"):
        config._parse('section1', '[section]\nfoo\n', 'mock/path.ini')

def test_parse_option_outside_of_section():
    config = Config(defaults={})
    with pytest.raises(errors.ConfigError, match=r"^mock/path.ini: Line 1: Option outside of section: foo = bar$"):
        config._parse('section1', 'foo = bar\n', 'mock/path.ini')

@patch('configparser.ConfigParser')
def test_parse_catches_generic_error(ConfigParser_mock):
    import configparser
    ConfigParser_mock.return_value.read_string.side_effect = configparser.Error('Something')
    config = Config(defaults={})
    with pytest.raises(errors.ConfigError, match=r"^mock/path.ini: Something$"):
        config._parse('section1', '', 'mock/path.ini')

def test_parse_returns_nested_dictionary():
    config = Config(defaults={})
    cfg = config._parse('section1', '[foo]\na = 1\nb = 2\n[bar]\n1 = one\n', 'mock/path.ini')
    assert cfg == {'foo': {'a': '1',
                           'b': '2'},
                   'bar': {'1': 'one'}}

def test_parse_uses_newlines_as_list_separator():
    config = Config(defaults={})
    cfg = config._parse('section1', '[foo]\na = 1\n 2\n    3\n', 'mock/path.ini')
    assert cfg == {'foo': {'a': ['1', '2', '3']}}


def test_defaults_returns_defaults_for_section():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    assert config.defaults('section1') == {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                           'subsection2': {'b': '4', 'c': '5', 'd': '6'}}
    assert config.defaults('section2') == {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                           'subsection3': {'y': '40', 'z': '50', '_': '60'}}
    with pytest.raises(ValueError, match=r'^No such section: section3$'):
        config.defaults('section3')

def test_defaults_raises_ValueError():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    with pytest.raises(ValueError, match=r'^No such section: section3$'):
        config.defaults('section3')


@patch('upsies.config._path_exists')
def test_read_does_not_ignore_nonexisting_path(path_exists_mock):
    config = Config(defaults={})
    path_exists_mock.return_value = False
    with pytest.raises(errors.ConfigError, match=r'^path/to/no/such/file.ini: No such file or directory$'):
        config.read('foo', 'path/to/no/such/file.ini')
    assert config._cfg == {}
    assert config._files == {}
    with pytest.raises(KeyError):
        config['foo']

@patch('upsies.config._path_exists')
def test_read_ignores_nonexisting_path(path_exists_mock):
    config = Config(defaults={})
    path_exists_mock.return_value = False
    assert config.read('foo', 'path/to/no/such/file.ini', ignore_missing=True) is None
    assert config._cfg == {'foo': {}}
    assert config._files == {'foo': 'path/to/no/such/file.ini'}
    assert config['foo'] == {}

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
        with pytest.raises(KeyError):
            config['foo']
    finally:
        filepath.chmod(0o660)

@pytest.mark.parametrize('ignore_missing', (True, False), ids=lambda v: f'ignore_missing={v!r}')
def test_read_succeeds(ignore_missing, tmp_path):
    file1 = tmp_path / 'file1.ini'
    file2 = tmp_path / 'file2.ini'
    file1.write_text('[foo]\na = b\n\n[bar]\nx = 1000\n  2000\n')
    file2.write_text('[something]\na = foo\n[foo]\nbar=Bar.\n')
    config = Config(defaults={
        'main': {'foo': {'a': None},
                 'bar': {'x': None}},
        'other': {'something': {'a': None},
                  'foo': {'bar': None,
                          'baz': 'hello'}},
    })
    assert config.read('main', file1, ignore_missing=ignore_missing) is None
    assert config.read('other', file2, ignore_missing=ignore_missing) is None
    assert config._cfg == {
        'main': {'foo': {'a': 'b'},
                 'bar': {'x': ['1000', '2000']}},
        'other': {'something': {'a': 'foo'},
                  'foo': {'bar': 'Bar.',
                          'baz': 'hello'}},
    }
    assert config._files == {'main': file1, 'other': file2}
    assert config['main'] == {'foo': {'a': 'b'},
                              'bar': {'x': ['1000', '2000']}}
    assert config['other'] == {'something': {'a': 'foo'},
                               'foo': {'bar': 'Bar.',
                                       'baz': 'hello'}}


@patch('upsies.config.Config.read')
def test_init_keyword_arguments(read_mock):
    Config(
        defaults={},
        foo='path/to/foo_file.ini',
        bar='path/to/bar_file.ini',
    )
    assert read_mock.call_args_list == [
        call('foo', 'path/to/foo_file.ini'),
        call('bar', 'path/to/bar_file.ini'),
    ]
