import argparse
import re
from unittest.mock import call, patch

import pytest

from upsies import defaults, errors, trackers, utils
from upsies.utils import argtypes


@pytest.mark.parametrize('client', utils.btclients.client_names())
def test_client_valid_value(client):
    assert argtypes.client(client) == client
    assert argtypes.client(client.upper()) == client
    assert argtypes.client(client.capitalize()) == client

def test_client_invalid_value():
    with pytest.raises(argparse.ArgumentTypeError, match=r'^Unsupported client: foo$'):
        argtypes.client('foo')


@pytest.mark.parametrize(
    argnames='path, path_exists, exp_exc',
    argvalues=(
        ('path/to/foo', True, None),
        ('path/to/foo', False, argparse.ArgumentTypeError('No such file or directory: path/to/foo')),
    ),
    ids=lambda v: str(v),
)
def test_content(path, path_exists, exp_exc, mocker):
    release_mock = mocker.patch('upsies.utils.argtypes.release', return_value='release/path')
    exists_mock = mocker.patch('os.path.exists', return_value=path_exists)
    if path_exists:
        assert argtypes.content(path) == release_mock.return_value
    else:
        with pytest.raises(type(exp_exc), match=rf'^{re.escape(str(exp_exc))}$'):
            argtypes.content(path)

    assert release_mock.call_args_list == [call(path)]
    assert exists_mock.call_args_list == [call(release_mock.return_value)]

@pytest.mark.parametrize('imghost', utils.imghosts.imghost_names())
def test_imghost_valid_value(imghost):
    assert argtypes.imghost(imghost) == imghost
    assert argtypes.imghost(imghost.upper()) == imghost
    assert argtypes.imghost(imghost.capitalize()) == imghost

def test_imghost_invalid_value():
    with pytest.raises(argparse.ArgumentTypeError, match=r'^Unsupported image hosting service: foo$'):
        argtypes.imghost('foo')


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
    assert argtypes.integer(value) == exp_value

@pytest.mark.parametrize('value', ('one', (1, 2, 3)), ids=lambda v: repr(v))
def test_integer_invalid_value(value):
    with pytest.raises(argparse.ArgumentTypeError, match=rf'^Not an integer: {re.escape(repr(value))}'):
        argtypes.integer(value)


@pytest.mark.parametrize(
    argnames='min, max, value, exp_value',
    argvalues=(
        (1, 5, 5.0, 5),
    ),
)
def test_number_of_screenshots_valid_value(min, max, value, exp_value):
    assert argtypes.number_of_screenshots(min=min, max=max)(value) == exp_value

@pytest.mark.parametrize(
    argnames='min, max, value, exp_error',
    argvalues=(
        (1, 5, 0, 'Minimum is 1'),
        (1, 5, 6, 'Maximum is 5'),
        (1, 5, 'asdf', "Invalid integer value: 'asdf'"),
    ),
)
def test_number_of_screenshots_invalid_value(min, max, value, exp_error):
    with pytest.raises(argparse.ArgumentTypeError, match=rf'^{re.escape(exp_error)}$'):
        argtypes.number_of_screenshots(min=min, max=max)(value)


@pytest.mark.parametrize('option', defaults.option_paths())
def test_option_valid_value(option):
    assert argtypes.option(option) == option

def test_option_invalid_value():
    with pytest.raises(argparse.ArgumentTypeError, match=r'^Unknown option: foo$'):
        argtypes.option('foo')


@pytest.mark.parametrize(
    argnames='path, exp_path, exc, exp_exc',
    argvalues=(
        ('path/to/foo', 'path/to/foo', None, None),
        (123, '123', None, None),
        ('path/to/foo', 'path/to/foo', errors.SceneError('bar'), argparse.ArgumentTypeError('bar')),
        ('path/to/foo', 'path/to/foo', RuntimeError('baz'), RuntimeError('baz')),
    ),
    ids=lambda v: str(v),
)
def test_release(path, exp_path, exc, exp_exc, mocker):
    mocker.patch('upsies.utils.scene.assert_not_abbreviated_filename',
                 side_effect=exc)
    if exp_exc:
        with pytest.raises(type(exp_exc), match=rf'^{re.escape(str(exp_exc))}$'):
            argtypes.release(path)
    else:
        assert argtypes.release(path) == exp_path


@pytest.mark.parametrize('scenedb', utils.scene.scenedb_names())
def test_scenedb_valid_value(scenedb):
    assert argtypes.scenedb(scenedb) == scenedb
    assert argtypes.scenedb(scenedb.upper()) == scenedb
    assert argtypes.scenedb(scenedb.capitalize()) == scenedb

def test_scenedb_invalid_value():
    with pytest.raises(argparse.ArgumentTypeError, match=r'^Unsupported scene release database: foo$'):
        argtypes.scenedb('foo')


@patch('upsies.utils.timestamp.parse')
def test_timestamp_valid_value(parse_mock):
    assert argtypes.timestamp('foo') is parse_mock.return_value
    assert parse_mock.call_args_list == [call('foo')]

@patch('upsies.utils.timestamp.parse')
@pytest.mark.parametrize('exception', (ValueError, TypeError))
def test_timestamp_invalid_value(parse_mock, exception):
    parse_mock.side_effect = exception('Message!')
    with pytest.raises(argparse.ArgumentTypeError, match=r'^Message!$'):
        argtypes.timestamp('foo')


@pytest.mark.parametrize('tracker', trackers.tracker_names())
def test_tracker_valid_value(tracker):
    assert argtypes.tracker(tracker) == tracker
    assert argtypes.tracker(tracker.upper()) == tracker
    assert argtypes.tracker(tracker.capitalize()) == tracker

def test_tracker_invalid_value():
    with pytest.raises(argparse.ArgumentTypeError, match=r'^Unsupported tracker: foo$'):
        argtypes.tracker('foo')


@pytest.mark.parametrize('webdb', utils.webdbs.webdb_names())
def test_webdb_valid_value(webdb):
    assert argtypes.webdb(webdb) == webdb
    assert argtypes.webdb(webdb.upper()) == webdb
    assert argtypes.webdb(webdb.capitalize()) == webdb

def test_webdb_invalid_value():
    with pytest.raises(argparse.ArgumentTypeError, match=r'^Unsupported database: foo$'):
        argtypes.webdb('foo')
