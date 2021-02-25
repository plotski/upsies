from unittest.mock import Mock, call

import pytest

from upsies.utils import btclients


def test_clients(mocker):
    existing_clients = (Mock(), Mock(), Mock())
    submodules_mock = mocker.patch('upsies.utils.btclients.submodules')
    subclasses_mock = mocker.patch('upsies.utils.btclients.subclasses', return_value=existing_clients)
    assert btclients.clients() == existing_clients
    assert submodules_mock.call_args_list == [call('upsies.utils.btclients')]
    assert subclasses_mock.call_args_list == [call(btclients.ClientApiBase, submodules_mock.return_value)]


def test_client_returns_ClientApiBase_instance(mocker):
    existing_clients = (Mock(), Mock(), Mock())
    existing_clients[0].configure_mock(name='foo')
    existing_clients[1].configure_mock(name='bar')
    existing_clients[2].configure_mock(name='baz')
    mocker.patch('upsies.utils.btclients.clients', return_value=existing_clients)
    assert btclients.client('bar', x=123) is existing_clients[1].return_value
    assert existing_clients[1].call_args_list == [call(x=123)]

def test_client_fails_to_find_client(mocker):
    existing_clients = (Mock(), Mock(), Mock())
    existing_clients[0].configure_mock(name='foo')
    existing_clients[1].configure_mock(name='bar')
    existing_clients[2].configure_mock(name='baz')
    mocker.patch('upsies.utils.btclients.clients', return_value=existing_clients)
    with pytest.raises(ValueError, match='^Unsupported client: bam$'):
        btclients.client('bam', x=123)
    for c in existing_clients:
        assert c.call_args_list == []


def test_client_names(mocker):
    existing_clients = (Mock(), Mock(), Mock())
    existing_clients[0].configure_mock(name='FOO')
    existing_clients[1].configure_mock(name='bar')
    existing_clients[2].configure_mock(name='Baz')
    mocker.patch('upsies.utils.btclients.clients', return_value=existing_clients)
    btclients.client_names() == ['bar', 'Baz', 'FOO']
