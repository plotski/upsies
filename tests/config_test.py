import os
from unittest.mock import call, patch

import pytest

from upsies import errors
from upsies.config import Config


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

@patch('upsies.config.Config.read')
def test_init_copies_defaults(read_mock):
    defaults = {'a': 'b'}
    c = Config(
        defaults=defaults,
        foo='path/to/foo_file.ini',
    )
    assert id(c._defaults) != id(defaults)
    assert id(c._cfg) != id(defaults)

@patch('upsies.config.Config.read')
def test_init_uses_defaults_as_initial_config(read_mock):
    defaults = {'section': {'subsection1': {'foo': 123, 'bar': 456},
                            'subsection2': {'foo': 123, 'bar': 456}}}
    c = Config(defaults=defaults)
    assert c._cfg == defaults


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


def test_parse_finds_duplicate_section():
    config = Config(defaults={})
    with pytest.raises(errors.ConfigError, match=r'^mock/path.ini: Line 3: asdf: Duplicate section$'):
        config._parse('section1', '[asdf]\nfoo = bar\n[asdf]\na = b\n', 'mock/path.ini')

def test_parse_finds_duplicate_option():
    config = Config(defaults={})
    with pytest.raises(errors.ConfigError, match=r'^mock/path.ini: Line 3: foo: Duplicate option$'):
        config._parse('section1', '[section]\nfoo = bar\nfoo = baz\n', 'mock/path.ini')

def test_parse_finds_invalid_syntax():
    config = Config(defaults={})
    with pytest.raises(errors.ConfigError, match=r"^mock/path.ini: Line 2: 'foo\\n': Invalid syntax$"):
        config._parse('section1', '[section]\nfoo\n', 'mock/path.ini')

def test_parse_option_outside_of_section():
    config = Config(defaults={})
    with pytest.raises(errors.ConfigError, match=r"^mock/path.ini: Line 1: foo = bar: Option outside of section$"):
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


def test_validate_section_finds_unknown_section():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    with pytest.raises(errors.ConfigError, match=r'^section5: Unknown section$'):
        config._validate_section('section5', {'foo': 'bar'}, 'path/to/section1.ini')

def test_validate_section_finds_unknown_subsection():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    with pytest.raises(errors.ConfigError, match=r'^path/to/section1.ini: foo: Unknown section$'):
        config._validate_section('section1', {'foo': {'bar': 'baz'}}, 'path/to/section1.ini')

def test_validate_section_finds_unknown_option():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    with pytest.raises(errors.ConfigError, match=r'^path/to/section1.ini: subsection2: bar: Unknown option$'):
        config._validate_section('section1', {'subsection2': {'bar': 'baz'}}, 'path/to/section1.ini')

def test_validate_section_returns_valid_config():
    config = Config(defaults={})
    config._defaults = {'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
                        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                                     'subsection3': {'y': '40', 'z': '50', '_': '60'}}}
    cfg = {'subsection2': {'b': '0'}}
    assert config._validate_section('section1', cfg, 'path/to/section1.ini') == cfg


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


def test_validate_path_without_subsection():
    config = Config(defaults={
        'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                     'subsection3': {'y': '40', 'z': '50', '_': '60'}},
    })
    with pytest.raises(errors.ConfigError, match=r'^section2: Missing subsection and option$'):
        config._validate_path('section2')

def test_validate_path_without_option():
    config = Config(defaults={
        'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                     'subsection3': {'y': '40', 'z': '50', '_': '60'}},
    })
    with pytest.raises(errors.ConfigError, match=r'^section2.subsection3: Missing option$'):
        config._validate_path('section2.subsection3')

def test_validate_path_with_unknown_section():
    config = Config(defaults={
        'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                     'subsection3': {'y': '40', 'z': '50', '_': '60'}},
    })
    with pytest.raises(errors.ConfigError, match=r'^foo: Unknown section$'):
        config._validate_path('foo.bar.baz')

def test_validate_path_with_unknown_subsection():
    config = Config(defaults={
        'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                     'subsection3': {'y': '40', 'z': '50', '_': '60'}},
    })
    with pytest.raises(errors.ConfigError, match=r'^bar: Unknown subsection in section section1$'):
        config._validate_path('section1.bar.baz')

def test_validate_path_with_unknown_option():
    config = Config(defaults={
        'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                     'subsection3': {'y': '40', 'z': '50', '_': '60'}},
    })
    with pytest.raises(errors.ConfigError, match=r'^baz: Unknown option in subsection section1.subsection2$'):
        config._validate_path('section1.subsection2.baz')

def test_validate_path_with_valid_path():
    config = Config(defaults={
        'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                     'subsection3': {'y': '40', 'z': '50', '_': '60'}},
    })
    assert config._validate_path('section1.subsection1.a') == ('section1', 'subsection1', 'a')
    assert config._validate_path('section1.subsection1.b') == ('section1', 'subsection1', 'b')
    assert config._validate_path('section1.subsection1.c') == ('section1', 'subsection1', 'c')

    assert config._validate_path('section1.subsection2.b') == ('section1', 'subsection2', 'b')
    assert config._validate_path('section1.subsection2.c') == ('section1', 'subsection2', 'c')
    assert config._validate_path('section1.subsection2.d') == ('section1', 'subsection2', 'd')

    assert config._validate_path('section2.subsection2.x') == ('section2', 'subsection2', 'x')
    assert config._validate_path('section2.subsection2.y') == ('section2', 'subsection2', 'y')
    assert config._validate_path('section2.subsection2.z') == ('section2', 'subsection2', 'z')

    assert config._validate_path('section2.subsection3.y') == ('section2', 'subsection3', 'y')
    assert config._validate_path('section2.subsection3.z') == ('section2', 'subsection3', 'z')
    assert config._validate_path('section2.subsection3._') == ('section2', 'subsection3', '_')


def test_sections_are_immutable():
    config = Config(defaults={
        'section': {'subsection': {'a': '1', 'b': '2', 'c': '3'}},
    })
    with pytest.raises(TypeError, match=r'does not support item assignment'):
        config['section'] = 'foo'

@pytest.mark.parametrize('key', ('section1', 'section1.subsection1', 'section1.subsection1.a'))
def test_subsections_are_immutable(key):
    config = Config(defaults={
        'section': {'subsection': {'a': '1', 'b': '2', 'c': '3'}},
    })
    print(config['section']['subsection'])
    with pytest.raises(TypeError, match=r'does not support item assignment'):
        config['section']['subsection'] = 'foo'

@pytest.mark.parametrize('key', ('section1', 'section1.subsection1', 'section1.subsection1.a'))
def test_options_are_immutable(key):
    config = Config(defaults={
        'section': {'subsection': {'a': '1', 'b': '2', 'c': '3'}},
    })
    print(config['section']['subsection'])
    with pytest.raises(TypeError, match=r'does not support item assignment'):
        config['section']['subsection']['a'] = 'foo'


def test_set_validates_path(mocker):
    config = Config(defaults={
        'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                     'subsection3': {'y': '40', 'z': '50', '_': '60'}},
    })
    mocker.patch.object(config, '_validate_path', side_effect=errors.ConfigError('invalid path'))
    with pytest.raises(errors.ConfigError, match=r'^invalid path$'):
        config.set('foo', 'bar')

def test_set_changes_value(mocker):
    config = Config(defaults={
        'section1': {'subsection1': {'a': '1', 'b': '2', 'c': '3'},
                     'subsection2': {'b': '4', 'c': '5', 'd': '6'}},
        'section2': {'subsection2': {'x': '10', 'y': '20', 'z': '30'},
                     'subsection3': {'y': '40', 'z': '50', '_': '60'}},
    })
    config.set('section2.subsection3.y', 'hello')
    assert config['section2']['subsection3']['y'] == 'hello'


@pytest.mark.parametrize(
    argnames='sections',
    argvalues=(
        (),
        ('File_1',),
        ('File_2',),
        ('File_1', 'File_2'),
    ),
    ids=lambda v: str(v),
)
def test_write_succeeds(sections, tmp_path):
    file1 = tmp_path / 'file1.ini'
    file2 = tmp_path / 'file2.ini'
    file1.write_text('[foo]\nbar = baz\n')
    file2.write_text('[foo]\nbar = baz\n')
    config = Config(
        defaults={
            'File_1': {'foo': {'bar': None}},
            'File_2': {'foo': {'bar': None}},
        },
        File_1=file1,
        File_2=file2,
    )
    config.set('File_1.foo.bar', 'config written')
    config.set('File_2.foo.bar', 'config written')
    config.write(*sections)
    if not sections:
        files_changed = (file1, file2)
    else:
        files_changed = []
        if 'File_1' in sections:
            files_changed.append(file1)
        if 'File_2' in sections:
            files_changed.append(file2)
    for f in files_changed:
        assert open(f).read() == '[foo]\nbar = config written\n\n'

def test_write_fails(tmp_path):
    file = tmp_path / 'file1.ini'
    file.write_text('[foo]\nbar = baz\n')
    config = Config(
        defaults={'main': {'foo': {'bar': None}}},
        main=file,
    )
    os.chmod(file, 0o000)
    try:
        with pytest.raises(errors.ConfigError, match=rf'^{file}: Permission denied$'):
            config.write('main')
    finally:
        os.chmod(file, 0o600)
