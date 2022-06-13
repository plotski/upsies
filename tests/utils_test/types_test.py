import re

import pytest

from upsies.utils import types


@pytest.mark.parametrize(
    argnames='value, exp_int',
    argvalues=(
        ('1', 1), ('-1', -1),
        ('0.1', 0), ('-0.1', 0),
        ('0.9', 0), ('-0.9', 0),
        ('100', 100), (100, 100), (100.0, 100),
    ),
)
def test_Integer_valid_values(value, exp_int):
    i = types.Integer(value)
    assert i == exp_int

@pytest.mark.parametrize(
    argnames='value',
    argvalues=('zero', 'foo'),
)
def test_Integer_invalid_values(value):
    with pytest.raises(ValueError, match=rf'^Invalid integer value: {value!r}$'):
        types.Integer(value)

def test_Integer_min_max_values():
    min = 0
    max = 10

    with pytest.raises(ValueError, match=rf'^Minimum is {min}$'):
        types.Integer(min - 1, min=min, max=max)
    with pytest.raises(ValueError, match=rf'^Maximum is {max}$'):
        types.Integer(max + 1, min=min, max=max)

    for value in range(min, max + 1):
        i = types.Integer(value, min=min, max=max)
        assert i == value

    i = types.Integer(min, min=min, max=max)
    assert i.min == min
    assert i.max == max

    with pytest.raises(ValueError, match=rf'^Minimum is {min}$'):
        type(i)(min - 1)
    with pytest.raises(ValueError, match=rf'^Maximum is {max}$'):
        type(i)(max + 1)

@pytest.mark.parametrize(
    argnames='value, min, max, exp_repr',
    argvalues=(
        (5, 0, 10, 'Integer(5, min=0, max=10)'),
    ),
)
def test_Integer_repr(value, min, max, exp_repr):
    i = types.Integer(value, min=min, max=max)
    assert repr(i) == exp_repr

def test_Integer_str():
    i = types.Integer(3, min=0, max=10)
    assert str(i) == '3'


@pytest.mark.parametrize(
    argnames='value, options',
    argvalues=(
        ('1', (1, 2, 3, 4)),
        (2, (1, 2, 3, 4)),
        (3, ('1', '2', '3', '4')),
        ('4', ('1', '2', '3', '4')),
    ),
)
def test_Choice_valid_values(value, options):
    choice = types.Choice(value, options)
    assert choice == str(choice)
    assert isinstance(choice, str)

@pytest.mark.parametrize(
    argnames='empty_ok, error_expected',
    argvalues=(
        (False, True),
        (True, False),
    ),
)
def test_Choice_empty_ok(empty_ok, error_expected):
    if error_expected:
        with pytest.raises(ValueError, match=r'^Not one of bar, foo: $'):
            types.Choice('', options=('foo', 'bar'), empty_ok=empty_ok)
    else:
        choice = types.Choice('', options=('foo', 'bar'), empty_ok=empty_ok)
        assert choice == ''

@pytest.mark.parametrize(
    argnames='value, options, exp_error',
    argvalues=(
        (0, (1, 2, 3, 4), 'Not one of 1, 2, 3, 4: 0'),
        ('foo', (1, 2, 3, 4), 'Not one of 1, 2, 3, 4: foo'),
    ),
)
def test_Choice_invalid_values(value, options, exp_error):
    with pytest.raises(ValueError, match=rf'^{re.escape(exp_error)}$'):
        types.Choice(value, options)

    choice = types.Choice(options[0], options)
    with pytest.raises(ValueError, match=rf'^{re.escape(exp_error)}$'):
        type(choice)(value)

def test_Choice_repr():
    choice = types.Choice('bar', options=('foo', 'bar', 'baz'))
    assert repr(choice) == "Choice('bar', options=('bar', 'baz', 'foo'))"


@pytest.mark.parametrize(
    argnames='string, exp_bool',
    argvalues=(
        ('true', True), ('false', False),
        ('yes', True), ('no', False),
        ('1', True), ('0', False),
        ('on', True), ('off', False),
        ('aye', True), ('nay', False),
    ),
)
def test_Bool_valid_values(string, exp_bool):
    bool = types.Bool(string)
    if exp_bool:
        assert bool
    else:
        assert not bool
    assert str(bool) == string

@pytest.mark.parametrize(
    argnames='string',
    argvalues=('da', 'nyet'),
)
def test_Bool_invalid_values(string):
    with pytest.raises(ValueError, match=rf'^Invalid boolean value: {string!r}$'):
        types.Bool(string)

@pytest.mark.parametrize(
    argnames='a, b',
    argvalues=(
        (types.Bool('yes'), types.Bool('true')),
        (types.Bool('yes'), True),
    ),
)
def test_Bool_equality(a, b):
    assert a == b
    assert b == a

@pytest.mark.parametrize(
    argnames='a, b',
    argvalues=(
        (types.Bool('yes'), types.Bool('false')),
        (types.Bool('yes'), False),
    ),
)
def test_Bool_inequality(a, b):
    assert a != b
    assert b != a

def test_Bool_attributes():
    assert types.Bool.truthy == ('true', 'yes', '1', 'on', 'aye')
    assert types.Bool.falsy == ('false', 'no', '0', 'off', 'nay')


@pytest.mark.parametrize('number', ('0', '1', '10', '11.5', '11.05', '99', '9999'))
@pytest.mark.parametrize('space', ('', ' '))
@pytest.mark.parametrize(
    argnames='prefix, multiplier',
    argvalues=(
        ('', 1),
        ('k', 1000),
        ('M', 1000**2),
        ('G', 1000**3),
        ('T', 1000**4),
        ('P', 1000**5),
        ('Ki', 1024),
        ('Mi', 1024**2),
        ('Gi', 1024**3),
        ('Ti', 1024**4),
        ('Pi', 1024**5),
    ),
)
@pytest.mark.parametrize('unit', ('', 'B'))
def test_Bytes_from_valid_string(number, space, prefix, multiplier, unit):
    bytes = types.Bytes(f'{number}{space}{prefix}{unit}')
    assert bytes == int(float(number) * multiplier)

@pytest.mark.parametrize(
    argnames='string, exp_msg',
    argvalues=(
        ('foo', 'Invalid size: foo'),
        ('10x', 'Invalid unit: x'),
        ('10kx', 'Invalid unit: kx'),
        ('10 Mx', 'Invalid unit: Mx'),
    ),
)
def test_Bytes_from_invalid_string(string, exp_msg):
    with pytest.raises(ValueError, match=rf'^{exp_msg}$'):
        types.Bytes(string)

@pytest.mark.parametrize(
    argnames='number, exp_string',
    argvalues=(
        (0, '0 B'),
        (1, '1 B'),
        (10, '10 B'),
        (999, '999 B'),
        (1000, '1 kB'),
        (1001, '1 kB'),
        (1000 * 1.5, '1.5 kB'),
        (1000 * 1.75, '1.75 kB'),
        (1000 * 1.799, '1.8 kB'),
        (1023, '1023 B'),
        (1024, '1 KiB'),
        (1025, '1 KiB'),
        (1024 * 1.5, '1.5 KiB'),
        (1024 * 1.75, '1.79 kB'),
        (1024 * 1.799, '1.8 KiB'),
        (1000**2, '1 MB'), (1000**3, '1 GB'), (1000**4, '1 TB'), (1000**5, '1 PB'),
        (1024**2, '1 MiB'), (1024**3, '1 GiB'), (1024**4, '1 TiB'), (1024**5, '1 PiB'),
    ),
)
def test_Bytes_as_string(number, exp_string):
    string = str(types.Bytes(number))
    assert string == exp_string

@pytest.mark.parametrize(
    argnames='number, decimal_places, prefix, trailing_zeros, exp_string',
    argvalues=(
        (0, 0, 'binary', True, '0 B'),
        (0, 0, 'decimal', False, '0 B'),
        (0, 1, 'binary', False, '0 B'),
        (0, 1, 'decimal', True, '0.0 B'),

        (1, 0, 'binary', True, '1 B'),
        (1, 0, 'decimal', False, '1 B'),
        (1, 3, 'binary', False, '1 B'),
        (1, 3, 'decimal', True, '1.000 B'),

        (999, 3, 'decimal', True, '999.000 B'),
        (1001, 3, 'decimal', True, '1.001 kB'),
        (1001, 4, 'decimal', True, '1.0010 kB'),
        (1001, 4, 'decimal', False, '1.001 kB'),

        (999, 3, 'binary', False, '999 B'),
        (1000, 2, 'binary', False, '1000 B'),
        (1000, 2, 'binary', True, '1000.00 B'),
        (1001, 1, 'binary', True, '1001.0 B'),

        (1024, 4, 'decimal', True, '1.0240 kB'),
        (1024, 3, 'decimal', True, '1.024 kB'),
        (1024, 2, 'decimal', True, '1.02 kB'),
        (1024, 1, 'decimal', True, '1.0 kB'),
        (1024, 1, 'decimal', False, '1 kB'),
        (1024, 0, 'decimal', True, '1 kB'),

        (1023, 0, 'binary', True, '1023 B'),
        (1023, 1, 'binary', True, '1023.0 B'),
        (1023, 1, 'binary', False, '1023 B'),

        (1024, 1, 'binary', True, '1.0 KiB'),
        (1024, 1, 'binary', False, '1 KiB'),
        (1024, 0, 'binary', True, '1 KiB'),

        (1025, 5, 'binary', True, '1.00098 KiB'),
        (1025, 4, 'binary', True, '1.0010 KiB'),
        (1025, 4, 'binary', False, '1.001 KiB'),
        (1025, 3, 'binary', True, '1.001 KiB'),
        (1025, 2, 'binary', True, '1.00 KiB'),
        (1025, 2, 'binary', False, '1 KiB'),

        (4000, 2, 'shortest', False, '4 kB'),
        (4096, 2, 'shortest', False, '4 KiB'),

        (100 * 1e6, 0, 'decimal', False, '100 MB'),
    ),
)
def test_Bytes_format(number, prefix, decimal_places, trailing_zeros, exp_string):
    string = types.Bytes(number).format(
        prefix=prefix,
        decimal_places=decimal_places,
        trailing_zeros=trailing_zeros,
    )
    assert string == exp_string

def test_Bytes_repr():
    b = types.Bytes(123)
    assert repr(b) == 'Bytes(123)'


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
    assert bool(getattr(types.ReleaseType, name)) is bool_value

@pytest.mark.parametrize(
    argnames=('name', 'exp_str'),
    argvalues=(
        ('movie', 'movie'),
        ('season', 'season'),
        ('series', 'season'),
        ('episode', 'episode'),
        ('unknown', 'unknown'),
    ),
)
def test_ReleaseType_string(name, exp_str):
    assert str(getattr(types.ReleaseType, name)) == exp_str

@pytest.mark.parametrize(
    argnames=('name', 'exp_repr'),
    argvalues=(
        ('movie', 'ReleaseType.movie'),
        ('season', 'ReleaseType.season'),
        ('series', 'ReleaseType.season'),
        ('episode', 'ReleaseType.episode'),
        ('unknown', 'ReleaseType.unknown'),
    ),
)
def test_ReleaseType_repr(name, exp_repr):
    assert repr(getattr(types.ReleaseType, name)) == exp_repr


@pytest.mark.parametrize(
    argnames=('name', 'bool_value'),
    argvalues=(
        ('true', True),
        ('false', False),
        ('renamed', False),
        ('altered', False),
        ('unknown', False),
    ),
)
def test_SceneCheckResult_truthiness(name, bool_value):
    assert bool(getattr(types.SceneCheckResult, name)) is bool_value

@pytest.mark.parametrize(
    argnames=('name', 'exp_str'),
    argvalues=(
        ('true', 'true'),
        ('false', 'false'),
        ('renamed', 'renamed'),
        ('altered', 'altered'),
        ('unknown', 'unknown'),
    ),
)
def test_SceneCheckResult_string(name, exp_str):
    assert str(getattr(types.SceneCheckResult, name)) == exp_str

@pytest.mark.parametrize(
    argnames=('name', 'exp_repr'),
    argvalues=(
        ('true', 'SceneCheckResult.true'),
        ('false', 'SceneCheckResult.false'),
        ('renamed', 'SceneCheckResult.renamed'),
        ('altered', 'SceneCheckResult.altered'),
        ('unknown', 'SceneCheckResult.unknown'),
    ),
)
def test_SceneCheckResult_repr(name, exp_repr):
    assert repr(getattr(types.SceneCheckResult, name)) == exp_repr
