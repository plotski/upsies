import pytest

from upsies.utils import types


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
