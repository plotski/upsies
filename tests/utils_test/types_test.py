import re
from unittest.mock import call, patch

import pytest

from upsies import constants
from upsies.utils import types


def test_BTCLIENT_NAMES():
    from upsies.utils import btclients
    client_names = {client.name for client in btclients.clients()}
    assert client_names == set(types.BTCLIENT_NAMES)

def test_IMGHOST_NAMES():
    from upsies.utils import imghosts
    imghost_names = {imghost.name for imghost in imghosts.imghosts()}
    assert imghost_names == set(types.IMGHOST_NAMES)

def test_SCENEDB_NAMES():
    from upsies.utils import scene
    scenedb_names = {scenedb.name for scenedb in scene.scenedbs()}
    assert scenedb_names == set(types.SCENEDB_NAMES)

def test_TRACKER_NAMES():
    from upsies import trackers
    tracker_names = {tracker.name for tracker in trackers.trackers()}
    assert tracker_names == set(types.TRACKER_NAMES)

def test_WEBDB_NAMES():
    from upsies.utils import webdbs
    webdb_names = {webdb.name for webdb in webdbs.webdbs()}
    assert webdb_names == set(types.WEBDB_NAMES)


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


@pytest.mark.parametrize('client', types.BTCLIENT_NAMES)
def test_client_valid_value(client):
    assert types.client(client) == client
    assert types.client(client.upper()) == client
    assert types.client(client.capitalize()) == client

def test_client_invalid_value():
    with pytest.raises(ValueError, match=r'^Unsupported client: foo$'):
        types.client('foo')


@pytest.mark.parametrize('imghost', types.IMGHOST_NAMES)
def test_imghost_valid_value(imghost):
    assert types.imghost(imghost) == imghost
    assert types.imghost(imghost.upper()) == imghost
    assert types.imghost(imghost.capitalize()) == imghost

def test_imghost_invalid_value():
    with pytest.raises(ValueError, match=r'^Unsupported image hosting service: foo$'):
        types.imghost('foo')


@pytest.mark.parametrize('scenedb', types.SCENEDB_NAMES)
def test_scenedb_valid_value(scenedb):
    assert types.scenedb(scenedb) == scenedb
    assert types.scenedb(scenedb.upper()) == scenedb
    assert types.scenedb(scenedb.capitalize()) == scenedb

def test_scenedb_invalid_value():
    with pytest.raises(ValueError, match=r'^Unsupported scene release database: foo$'):
        types.scenedb('foo')


@pytest.mark.parametrize('tracker', types.TRACKER_NAMES)
def test_tracker_valid_value(tracker):
    assert types.tracker(tracker) == tracker
    assert types.tracker(tracker.upper()) == tracker
    assert types.tracker(tracker.capitalize()) == tracker

def test_tracker_invalid_value():
    with pytest.raises(ValueError, match=r'^Unsupported tracker: foo$'):
        types.tracker('foo')


@pytest.mark.parametrize('webdb', types.WEBDB_NAMES)
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
