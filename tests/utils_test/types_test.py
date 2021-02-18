import pytest

from upsies.utils import types


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
