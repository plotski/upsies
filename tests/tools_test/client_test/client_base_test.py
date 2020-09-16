import pytest

from upsies import errors
from upsies.tools.client._base import ClientApiBase

abstract_methods = (
    'name', 'add_torrent'
)

@pytest.mark.parametrize('method', abstract_methods)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in abstract_methods}
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
