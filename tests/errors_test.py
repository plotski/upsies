from unittest.mock import Mock

import pytest

from upsies import errors


def error_classes():
    clses = []
    for name in dir(errors):
        if not name.startswith('_'):
            cls = getattr(errors, name)
            if isinstance(cls, type) and issubclass(cls, Exception):
                clses.append(cls)
    return clses


@pytest.mark.parametrize(
    argnames='cls',
    argvalues=error_classes(),
)
def test_equality(cls):
    try:
        assert cls('foo') == cls('foo')
        assert cls('foo') != cls('bar')
        assert cls('foo') != ValueError('foo')
    # Some exceptions require more arguments
    except TypeError:
        pass


def test_RequestError_headers():
    e = errors.RequestError('foo', headers={'a': 1, 'b': 2})
    assert e.headers == {'a': 1, 'b': 2}

def test_RequestError_status_code():
    e = errors.RequestError('foo', status_code=123)
    assert e.status_code == 123


def test_SubprocessError():
    e = TypeError('foo')
    traceback = 'mock traceback'
    subproc_e = errors.SubprocessError(e, traceback)
    assert subproc_e.original_traceback == 'Subprocess traceback:\nmock traceback'


def test_SceneRenamedError_name_attributes():
    e = errors.SceneRenamedError(original_name='foo', existing_name='bar')
    assert e.original_name == 'foo'
    assert e.existing_name == 'bar'

def test_SceneRenamedError_url_attribute_without_release_url(mocker):
    scenedb_mock = mocker.patch('upsies.utils.scene.scenedb')
    del scenedb_mock.return_value.release_url
    e = errors.SceneRenamedError(original_name='foo', existing_name='bar')
    assert e.url is None

def test_SceneRenamedError_url_attribute_with_release_url(mocker):
    scenedb_mock = mocker.patch(
        'upsies.utils.scene.scenedb',
        return_value=Mock(release_url=Mock(return_value='http://foo')),
    )
    e = errors.SceneRenamedError(original_name='foo', existing_name='bar')
    assert e.url == 'http://foo'


def test_SceneFileSizeError(mocker):
    e = errors.SceneFileSizeError(
        filename='foo',
        original_size=123,
        existing_size=124,
    )
    assert e.filename == 'foo'
    assert e.original_size == 123
    assert e.existing_size == 124


def test_SceneMissingInfoError(mocker):
    e = errors.SceneMissingInfoError('foo.mkv')
    assert str(e) == 'Missing information: foo.mkv'
