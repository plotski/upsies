from unittest.mock import Mock, call

import pytest

from upsies.utils import imghosts


def test_imghosts(mocker):
    existing_imghosts = (Mock(), Mock(), Mock())
    submodules_mock = mocker.patch('upsies.utils.imghosts.submodules')
    subclasses_mock = mocker.patch('upsies.utils.imghosts.subclasses', return_value=existing_imghosts)
    assert imghosts.imghosts() == existing_imghosts
    assert submodules_mock.call_args_list == [call('upsies.utils.imghosts')]
    assert subclasses_mock.call_args_list == [call(imghosts.base.ImageHostBase, submodules_mock.return_value)]


def test_imghost_returns_ImageHostBase_instance(mocker):
    existing_imghosts = (Mock(), Mock(), Mock())
    existing_imghosts[0].configure_mock(name='foo')
    existing_imghosts[1].configure_mock(name='bar')
    existing_imghosts[2].configure_mock(name='baz')
    mocker.patch('upsies.utils.imghosts.imghosts', return_value=existing_imghosts)
    assert imghosts.imghost('bar', config={'foo': 'bar'}) is existing_imghosts[1].return_value
    assert existing_imghosts[1].call_args_list == [call(config={'foo': 'bar'})]

def test_imghost_fails_to_find_imghost(mocker):
    existing_imghosts = (Mock(), Mock(), Mock())
    existing_imghosts[0].configure_mock(name='foo')
    existing_imghosts[1].configure_mock(name='bar')
    existing_imghosts[2].configure_mock(name='baz')
    mocker.patch('upsies.utils.imghosts.imghosts', return_value=existing_imghosts)
    with pytest.raises(ValueError, match='^Unsupported image hosting service: bam$'):
        imghosts.imghost('bam')
    for ih in existing_imghosts:
        assert ih.call_args_list == []


def test_imghost_names(mocker):
    existing_imghosts = (Mock(), Mock(), Mock())
    existing_imghosts[0].configure_mock(name='FOO')
    existing_imghosts[1].configure_mock(name='bar')
    existing_imghosts[2].configure_mock(name='Baz')
    mocker.patch('upsies.utils.imghosts.imghosts', return_value=existing_imghosts)
    imghosts.imghost_names() == ['bar', 'Baz', 'FOO']
