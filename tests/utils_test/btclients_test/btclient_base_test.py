import pytest

from upsies import errors
from upsies.utils import btclients


def make_TestClientApi(default_config=None, **kwargs):
    # Avoid NameError bug
    default_config_ = default_config

    class TestClientApi(btclients.ClientApiBase):
        name = 'testorrent'
        default_config = default_config_ or {}

        async def add_torrent(self, torrent_path, download_path=None):
            pass

    return TestClientApi(**kwargs)


def test_name_property():
    print(make_TestClientApi)
    client = make_TestClientApi()
    assert client.name == 'testorrent'


def test_config_property():
    client = make_TestClientApi()
    assert client.config == {}
    client = make_TestClientApi(default_config={'foo': 1, 'bar': 2})
    assert client.config == {'foo': 1, 'bar': 2}
    client = make_TestClientApi(default_config={'foo': 1, 'bar': 2}, config={'bar': 99})
    assert client.config == {'foo': 1, 'bar': 99}


def test_read_torrent_file_returns_bytes(tmp_path):
    torrent_file = tmp_path / 'file.torrent'
    torrent_file.write_text('test data')
    data = btclients.ClientApiBase.read_torrent_file(torrent_file)
    assert data == b'test data'

def test_read_torrent_file_raises_TorrentError(tmp_path):
    torrent_file = tmp_path / 'file.torrent'
    torrent_file.write_text('test data')
    torrent_file.chmod(0o000)
    try:
        with pytest.raises(errors.TorrentError, match=rf'^{torrent_file}: Permission denied$'):
            btclients.ClientApiBase.read_torrent_file(torrent_file)
    finally:
        torrent_file.chmod(0o600)
