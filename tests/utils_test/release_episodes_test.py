import re
from unittest.mock import call

import pytest

from upsies.utils import release


def test_Episodes_init(mocker):
    set_mock = mocker.patch('upsies.utils.release.Episodes._set')
    release.Episodes('foo', bar='baz')
    assert set_mock.call_args_list == [call('foo', bar='baz')]


@pytest.mark.parametrize(
    argnames='clear',
    argvalues=(None, False, True),
)
def test_Episodes_update(clear, mocker):
    set_mock = mocker.patch('upsies.utils.release.Episodes._set')
    e = release.Episodes('initial', arg='uments')
    initial_e = dict(e)

    if clear is not None:
        e.update('foo', bar='baz', clear=clear)
    else:
        e.update('foo', bar='baz')

    assert set_mock.call_args_list == [
        call('initial', arg='uments'),
        call('foo', bar='baz'),
    ]

    if clear:
        assert e == {}
    else:
        assert e == initial_e


@pytest.mark.parametrize(
    argnames='initial, update_args, update_kwargs, exp_result',
    argvalues=(
        # Setting positional arguments
        (
            # Initial episodes
            {'1': ['2', '3'], '4': [], '': [6, '6', '5']},
            # Positional arguments
            ({'1': ['20', '30'], '40': [], '': ['60', 5, '50'], '10': '100'},),
            # Keyword arguments
            {},
            # Combined (initial + positional + keyword)
            {'1': ['2', '3', '20', '30'], '4': [], '40': [], '': ['5', '6', '50', '60'], '10': ['100']},
        ),
        # Setting keyword arguments
        (
            # Initial episodes
            {'1': ['2', '3'], '4': [], '': [6, '6', '5']},
            # Positional arguments
            (),
            # Keyword arguments
            {'S01': ['E20', 'E30'], 'S40': [], 'S': ['E60', 5, 'E50'], 'S10': 'E100'},
            # Combined (initial + positional + keyword)
            {'1': ['2', '3', '20', '30'], '4': [], '40': [], '': ['5', '6', '50', '60'], '10': ['100']},
        ),
        # Setting positional and keyword arguments
        (
            # Initial episodes
            {'1': ['2', '3'], '4': [], '': [6, '6', '5']},
            # Positional arguments
            ({'1': ['20', '40'], '': ['60'], '10': ['100']},),
            # Keyword arguments
            {'S01': ['E30', '50'], 'S40': [], 'S': [5, 'E50']},
            # Combined (initial + positional + keyword)
            {'1': ['2', '3', '20', '30', '40', '50'], '4': [], '40': [], '': ['5', '6', '50', '60'], '10': ['100']},
        ),
    ),
    ids=lambda v: str(v),
)
def test_Episodes_set(initial, update_args, update_kwargs, exp_result, mocker):
    e = release.Episodes(initial)
    e._set(*update_args, **update_kwargs)
    assert e == exp_result


def test_Episodes_normalize_season(mocker):
    e = release.Episodes()
    mocker.patch.object(e, '_normalize', return_value='mock number')
    season = e._normalize_season('foo')
    assert season == 'mock number'
    assert e._normalize.call_args_list == [call('foo', name='season', prefix='S', empty_string_ok=True)]


def test_Episodes_normalize_episode(mocker):
    e = release.Episodes()
    mocker.patch.object(e, '_normalize', return_value='mock number')
    episode = e._normalize_episode('foo')
    assert episode == 'mock number'
    assert e._normalize.call_args_list == [call('foo', name='episode', prefix='E', empty_string_ok=False)]


@pytest.mark.parametrize(
    argnames='value, name, prefix, empty_string_ok, exp_return_value, exp_exception',
    argvalues=(
        # Integer
        (-1, 'potatoe', 'P', None, None, TypeError('Invalid potatoe: -1')),
        (0, 'potatoe', 'P', None, '0', None),
        (1, 'potatoe', 'P', None, '1', None),

        # String
        ('-1', 'potatoe', 'P', None, None, TypeError("Invalid potatoe: '-1'")),
        ('0', 'potatoe', 'P', None, '0', None),
        ('1', 'potatoe', 'P', None, '1', None),
        ('P2', 'potatoe', 'P', None, '2', None),
        ('p3', 'potatoe', 'P', None, '3', None),
        ('P04', 'potatoe', 'P', None, '4', None),
        ('p05', 'potatoe', 'P', None, '5', None),
        ('PP6', 'potatoe', 'P', None, None, TypeError("Invalid potatoe: 'P6'")),

        # Empty string
        ('', 'potatoe', 'P', None, None, TypeError("Invalid potatoe: ''")),
        ('', 'potatoe', 'P', False, None, TypeError("Invalid potatoe: ''")),
        ('', 'potatoe', 'P', True, '', None),
        ('P', 'potatoe', 'P', None, None, TypeError("Invalid potatoe: ''")),
        ('P', 'potatoe', 'P', False, None, TypeError("Invalid potatoe: ''")),
        ('P', 'potatoe', 'P', True, '', None),
        ('p', 'potatoe', 'P', None, None, TypeError("Invalid potatoe: ''")),
        ('p', 'potatoe', 'P', False, None, TypeError("Invalid potatoe: ''")),
        ('p', 'potatoe', 'P', True, '', None),
        ('pp', 'potatoe', 'P', True, None, TypeError("Invalid potatoe: 'p'")),
        ('PP', 'potatoe', 'P', True, None, TypeError("Invalid potatoe: 'P'")),

        # Other types
        (1.2, 'potatoe', 'P', None, None, TypeError("Invalid potatoe: 1.2")),
        ([1, 2, 3], 'potatoe', 'P', None, None, TypeError("Invalid potatoe: [1, 2, 3]")),
    ),
    ids=lambda v: str(v),
)
def test_Episodes_normalize(value, name, prefix, empty_string_ok, exp_return_value, exp_exception):
    e = release.Episodes()

    kwargs = {
        'name': name,
        'prefix': prefix,
        'empty_string_ok': empty_string_ok,
    }
    # Remove `None` values
    for k, v in tuple(kwargs.items()):
        if v is None:
            del kwargs[k]

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            print(e._normalize(value, **kwargs))
    else:
        return_value = e._normalize(value, **kwargs)
        assert return_value == exp_return_value


@pytest.mark.parametrize(
    argnames=('string', 'exp'),
    argvalues=(
        ('foo.E01 bar', {'': ['1',]}),
        ('foo E01E2.bar', {'': ['1', '2']}),
        ('foo.bar.E01E2S03', {'': ['1', '2'], '3': []}),
        ('E01E2S03E04E05.baz', {'': ['1', '2'], '3': ['4', '5']}),
        ('S09E08S03E06S9E1', {'9': ['1', '8',], '3': ['6',]}),
        ('E01S03E06.bar.E02', {'': ['1', '2',], '3': ['6',]}),
    ),
    ids=lambda v: str(v),
)
def test_Episodes_from_string(string, exp):
    assert release.Episodes.from_string(string) == exp
    assert release.Episodes.from_string(string.lower()) == exp


@pytest.mark.parametrize(
    argnames=('sequence', 'exp'),
    argvalues=(
        (('foo.S01E01.bar', 'foo.S01E02.baz'), {'1': ['1', '2']}),
        (('foo.S02E02E01.bar', 'foo.S01E01.bar', 'foo.S02E03.baz'), {'1': ['1',], '2': ['1', '2', '3']}),
    ),
    ids=lambda v: str(v),
)
def test_Episodes_from_sequence(sequence, exp):
    assert release.Episodes.from_sequence(sequence) == exp


@pytest.mark.parametrize(
    argnames=('mapping', 'string'),
    argvalues=(
        ({'': [1,]}, 'E01'),
        ({'': [1, 10]}, 'E01E10'),
        ({4: [1, 10]}, 'S04E01E10'),
        ({2: [4,], 1: [2, 3]}, 'S01E02E03S02E04'),
        ({1: [2, 3], 2: [4,], '': [5,]}, 'E05S01E02E03S02E04'),
    ),
    ids=lambda v: str(v),
)
def test_Episodes_str(mapping, string):
    assert str(release.Episodes(mapping)) == string


def test_Episodes_repr():
    x = release.Episodes({5: [3, 6], '': [1, 2], 6: []})
    assert repr(x) == "Episodes({'5': ['3', '6'], '': ['1', '2'], '6': []})"


@pytest.mark.parametrize(
    argnames=('release_name', 'exp_value'),
    argvalues=(
        ('Foo.S01.720p.BluRay.x264-ASDF', True),
        ('Foo.S01E02.720p.BluRay.x264-ASDF', True),
        ('Foo.S01S02.720p.BluRay.x264-ASDF', True),
        ('Foo.S01E01E02.720p.BluRay.x264-ASDF', True),
        ('Foo.2015.S01.720p.BluRay.x264-ASDF', True),
        ('Foo.2015.S01E02.720p.BluRay.x264-ASDF', True),
        ('Foo.2015.S01S02.720p.BluRay.x264-ASDF', True),
        ('Foo.2015.S01E01E02.720p.BluRay.x264-ASDF', True),
        ('Foo.2015.720p.BluRay.x264-ASDF', False),
    ),
    ids=lambda v: str(v),
)
def test_has_episodes_info(release_name, exp_value):
    assert release.Episodes.has_episodes_info(release_name) is exp_value
    assert release.Episodes.has_episodes_info(release_name.lower()) is exp_value


@pytest.mark.parametrize(
    argnames=('string', 'exp_value'),
    argvalues=(
        ('S01', True),
        ('S01E02', True),
        ('S01E02E03', True),
        ('S01S02', True),
        ('S01S02E03', True),
        ('S01E02S03E04', True),
        ('S01E02E03S04E05S06', True),
        ('E01E02', True),
        ('.S01', False),
        ('S01.', False),
    ),
    ids=lambda v: str(v),
)
def test_is_episodes_info(string, exp_value):
    assert release.Episodes.is_episodes_info(string) is exp_value
    assert release.Episodes.is_episodes_info(string.lower()) is exp_value


@pytest.mark.parametrize(
    argnames=('episodes', 'exp_episodes'),
    argvalues=(
        ({}, {}),
        ({'': ('1',)}, {}),
        ({'1': (), '2': ('3',)}, {'1': (), '2': ()}),
    ),
    ids=lambda v: str(v),
)
def test_remove_specific_episodes(episodes, exp_episodes):
    e = release.Episodes(episodes)
    e.remove_specific_episodes()
    assert e == exp_episodes
