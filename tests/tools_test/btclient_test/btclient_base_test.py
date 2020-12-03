from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.tools import btclient


def test_clients(mocker):
    existing_clients = (Mock(), Mock(), Mock())
    submodules_mock = mocker.patch('upsies.utils.submodules')
    subclasses_mock = mocker.patch('upsies.utils.subclasses', return_value=existing_clients)
    assert btclient.clients() == existing_clients
    assert submodules_mock.call_args_list == [call('upsies.tools.btclient')]
    assert subclasses_mock.call_args_list == [call(btclient.ClientApiBase, submodules_mock.return_value)]


def test_client_returns_ClientApiBase_instance(mocker):
    clients = (Mock(), Mock(), Mock())
    clients[0].configure_mock(name='foo')
    clients[1].configure_mock(name='bar')
    clients[2].configure_mock(name='baz')
    mocker.patch('upsies.tools.btclient.clients', return_value=clients)
    assert btclient.client('bar', x=123) is clients[1].return_value
    assert clients[1].call_args_list == [call(x=123)]

def test_client_fails_to_find_client(mocker):
    clients = (Mock(), Mock(), Mock())
    clients[0].configure_mock(name='foo')
    clients[1].configure_mock(name='bar')
    clients[2].configure_mock(name='baz')
    mocker.patch('upsies.tools.btclient.clients', return_value=clients)
    with pytest.raises(ValueError, match='^Unsupported client: bam$'):
        btclient.client('bam', x=123)
    for c in clients:
        assert c.call_args_list == []


@pytest.mark.parametrize('method', btclient.ClientApiBase.__abstractmethods__)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in btclient.ClientApiBase.__abstractmethods__}
    del attrs[method]
    cls = type('TestClientApi', (btclient.ClientApiBase,), attrs)
    # Python 3.9 changed "methods" to "method"
    exp_msg = rf"^Can't instantiate abstract class TestClientApi with abstract methods? {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def test_read_torrent_file_returns_bytes(tmp_path):
    torrent_file = tmp_path / 'file.torrent'
    torrent_file.write_text('test data')
    data = btclient.ClientApiBase.read_torrent_file(torrent_file)
    assert data == b'test data'

def test_read_torrent_file_raises_TorrentError(tmp_path):
    torrent_file = tmp_path / 'file.torrent'
    torrent_file.write_text('test data')
    torrent_file.chmod(0o000)
    try:
        with pytest.raises(errors.TorrentError, match=rf'^{torrent_file}: Permission denied$'):
            btclient.ClientApiBase.read_torrent_file(torrent_file)
    finally:
        torrent_file.chmod(0o600)
