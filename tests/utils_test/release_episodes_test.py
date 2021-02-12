import re

import pytest

from upsies.utils import release


@pytest.mark.parametrize(
    argnames=('args', 'exp', 'exc', 'msg'),
    argvalues=(
        ({1: [1, 2], '2': ('3', '4')}, {'1': ('1', '2'), '2': ('3', '4')}, None, None),
        (((1, [1, 2]), (('2', ('3', '4')))), {'1': ('1', '2'), '2': ('3', '4')}, None, None),
        ({1: [1, 2], '': ('3', '4')}, {'1': ('1', '2'), '': ('3', '4')}, None, None),
        ({1: [1, 2], '2': 3}, None, TypeError, "Invalid episodes: 3"),
        ({1: [1, 2], 'x': ('3', '4')}, None, ValueError, "Invalid season: 'x'"),
        ({1: [1, 2], '2': ('3', 'x')}, None, ValueError, "Invalid episode: 'x'"),
        ({1: [1, 2], ('2',): ('3', '4')}, None, TypeError, "Invalid season: ('2',)"),
        ({1: [1, 2], '2': ('3', ['4'])}, None, TypeError, "Invalid episode: ['4']"),
    ),
    ids=lambda v: str(v),
)
def test_Episodes_validation(args, exp, exc, msg):
    if exp is not None:
        print(f'assert release.Episodes({args!r}) == {exp!r}')
        assert release.Episodes(args) == exp
    else:
        with pytest.raises(exc, match=rf'^{re.escape(msg)}$'):
            print(release.Episodes(args))


@pytest.mark.parametrize(
    argnames=('string', 'exp'),
    argvalues=(
        ('foo.E01 bar', {'': ('1',)}),
        ('foo E01E2.bar', {'': ('1', '2')}),
        ('foo.bar.E01E2S03', {'': ('1', '2'), '3': ()}),
        ('E01E2S03E04E05.baz', {'': ('1', '2'), '3': ('4', '5')}),
        ('S09E08S03E06S9E1', {'9': ('1', '8',), '3': ('6',)}),
        ('E01S03E06.bar.E02', {'': ('1', '2',), '3': ('6',)}),
    ),
    ids=lambda v: str(v),
)
def test_Episodes_from_string(string, exp):
    assert release.Episodes.from_string(string) == exp


@pytest.mark.parametrize(
    argnames=('mapping', 'string'),
    argvalues=(
        ({'': (1,)}, 'E01'),
        ({'': (1, 10)}, 'E01E10'),
        ({4: (1, 10)}, 'S04E01E10'),
        ({2: (4,), 1: (2, 3)}, 'S01E02E03S02E04'),
        ({1: (2, 3), 2: (4,), '': (5,)}, 'E05S01E02E03S02E04'),
    ),
    ids=lambda v: str(v),
)
def test_Episodes_str(mapping, string):
    assert str(release.Episodes(mapping)) == string


def test_Episodes_repr():
    x = release.Episodes({5: (3, 6), '': (1, 2), 6: ()})
    assert repr(x) == "Episodes({'5': ('3', '6'), '': ('1', '2'), '6': ()})"


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
    ),
    ids=lambda v: str(v),
)
def test_has_episodes_info(release_name, exp_value):
    assert release.Episodes.has_episodes_info(release_name) == exp_value
    assert release.Episodes.has_episodes_info(release_name.lower()) == exp_value
