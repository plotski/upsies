from unittest.mock import Mock, call

import pytest

from upsies.utils import webdbs


def test_webdbs(mocker):
    existing_webdbs = (Mock(), Mock(), Mock())
    submodules_mock = mocker.patch('upsies.utils.webdbs.submodules')
    subclasses_mock = mocker.patch('upsies.utils.webdbs.subclasses', return_value=existing_webdbs)
    assert webdbs.webdbs() == existing_webdbs
    assert submodules_mock.call_args_list == [call('upsies.utils.webdbs')]
    assert subclasses_mock.call_args_list == [call(webdbs.WebDbApiBase, submodules_mock.return_value)]


def test_webdb_returns_WebdbApiBase_instance(mocker):
    existing_webdbs = (Mock(), Mock(), Mock())
    existing_webdbs[0].configure_mock(name='foo')
    existing_webdbs[1].configure_mock(name='bar')
    existing_webdbs[2].configure_mock(name='baz')
    mocker.patch('upsies.utils.webdbs.webdbs', return_value=existing_webdbs)
    assert webdbs.webdb('bar', x=123) is existing_webdbs[1].return_value
    assert existing_webdbs[1].call_args_list == [call(x=123)]

def test_webdb_fails_to_find_webdb(mocker):
    existing_webdbs = (Mock(), Mock(), Mock())
    existing_webdbs[0].configure_mock(name='foo')
    existing_webdbs[1].configure_mock(name='bar')
    existing_webdbs[2].configure_mock(name='baz')
    mocker.patch('upsies.utils.webdbs.webdbs', return_value=existing_webdbs)
    with pytest.raises(ValueError, match='^Unsupported web database: bam$'):
        webdbs.webdb('bam', x=123)
    for c in existing_webdbs:
        assert c.call_args_list == []
