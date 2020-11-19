from unittest.mock import call, patch

import pytest

from upsies import errors
from upsies.tools.btclient import ClientApiBase, client


@patch('upsies.tools.btclient.foo', create=True)
def test_client_returns_ClientApi_instance(foo_module):
    c = client('foo', bar='baz')
    assert c is foo_module.ClientApi.return_value
    assert foo_module.ClientApi.call_args_list == [call(bar='baz')]

def test_client_fails_to_find_module():
    with pytest.raises(ValueError, match='^Unsupported client: foo$'):
        client('foo', bar='baz')


@pytest.mark.parametrize('method', ClientApiBase.__abstractmethods__)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in ClientApiBase.__abstractmethods__}
    del attrs[method]
    cls = type('ClientApi', (ClientApiBase,), attrs)
    # Python 3.9 changed "methods" to "method"
    exp_msg = rf"^Can't instantiate abstract class ClientApi with abstract methods? {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def test_read_torrent_file_returns_bytes(tmp_path):
    torrent_file = tmp_path / 'file.torrent'
    torrent_file.write_text('test data')
    data = ClientApiBase.read_torrent_file(torrent_file)
    assert data == b'test data'

def test_read_torrent_file_raises_TorrentError(tmp_path):
    torrent_file = tmp_path / 'file.torrent'
    torrent_file.write_text('test data')
    torrent_file.chmod(0o000)
    try:
        with pytest.raises(errors.TorrentError, match=rf'^{torrent_file}: Permission denied$'):
            ClientApiBase.read_torrent_file(torrent_file)
    finally:
        torrent_file.chmod(0o600)
