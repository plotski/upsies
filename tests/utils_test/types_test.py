import re
from unittest.mock import call, patch

import pytest

from upsies import constants
from upsies.utils import types


@pytest.mark.parametrize(
    argnames='value, exp_value',
    argvalues=(
        (123, 123),
        (123.2, 123),
        ('123', 123),
        ('123.2', 123),
    ),
    ids=lambda v: repr(v),
)
def test_integer_valid_value(value, exp_value):
    assert types.integer(value) == exp_value

@pytest.mark.parametrize('value', ('one', (1, 2, 3)), ids=lambda v: repr(v))
def test_integer_invalid_value(value):
    with pytest.raises(ValueError, match=rf'^Not an integer: {re.escape(repr(value))}'):
        types.integer(value)


@patch('upsies.utils.timestamp.parse')
def test_timestamp_valid_value(parse_mock):
    assert types.timestamp('foo') is parse_mock.return_value
    assert parse_mock.call_args_list == [call('foo')]

@patch('upsies.utils.timestamp.parse')
@pytest.mark.parametrize('exception', (ValueError, TypeError))
def test_timestamp_invalid_value(parse_mock, exception):
    parse_mock.side_effect = exception('Message!')
    with pytest.raises(ValueError, match=r'^Message!$'):
        types.timestamp('foo')


@pytest.mark.parametrize('client', constants.BTCLIENT_NAMES)
def test_client_valid_value(client):
    assert types.client(client) == client
    assert types.client(client.upper()) == client
    assert types.client(client.capitalize()) == client

def test_client_invalid_value():
    with pytest.raises(ValueError, match=r'^Unsupported client: foo$'):
        types.client('foo')


@pytest.mark.parametrize('imghost', constants.IMGHOST_NAMES)
def test_imghost_valid_value(imghost):
    assert types.imghost(imghost) == imghost
    assert types.imghost(imghost.upper()) == imghost
    assert types.imghost(imghost.capitalize()) == imghost

def test_imghost_invalid_value():
    with pytest.raises(ValueError, match=r'^Unsupported image hosting service: foo$'):
        types.imghost('foo')


@pytest.mark.parametrize('scenedb', constants.SCENEDB_NAMES)
def test_scenedb_valid_value(scenedb):
    assert types.scenedb(scenedb) == scenedb
    assert types.scenedb(scenedb.upper()) == scenedb
    assert types.scenedb(scenedb.capitalize()) == scenedb

def test_scenedb_invalid_value():
    with pytest.raises(ValueError, match=r'^Unsupported scene release database: foo$'):
        types.scenedb('foo')


@pytest.mark.parametrize('tracker', constants.TRACKER_NAMES)
def test_tracker_valid_value(tracker):
    assert types.tracker(tracker) == tracker
    assert types.tracker(tracker.upper()) == tracker
    assert types.tracker(tracker.capitalize()) == tracker

def test_tracker_invalid_value():
    with pytest.raises(ValueError, match=r'^Unsupported tracker: foo$'):
        types.tracker('foo')


@pytest.mark.parametrize('webdb', constants.WEBDB_NAMES)
def test_webdb_valid_value(webdb):
    assert types.webdb(webdb) == webdb
    assert types.webdb(webdb.upper()) == webdb
    assert types.webdb(webdb.capitalize()) == webdb

def test_webdb_invalid_value():
    with pytest.raises(ValueError, match=r'^Unsupported database: foo$'):
        types.webdb('foo')


@pytest.mark.parametrize('option', constants.OPTION_PATHS)
def test_option_valid_value(option):
    assert types.option(option) == option

def test_option_invalid_value():
    with pytest.raises(ValueError, match=r'^Unknown option: foo$'):
        types.option('foo')


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
