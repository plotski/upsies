import base64

from upsies.trackers.bb import BbTrackerConfig


def test_defaults():
    assert BbTrackerConfig() == {
        'base_url'   : base64.b64decode('aHR0cHM6Ly9iYWNvbmJpdHMub3Jn').decode('ascii'),
        'username'   : '',
        'password'   : '',
        'announce'   : '',
        'exclude'    : [],
        'source'     : 'bB',
        'image_host' : 'imgbox',
        'add-to'     : '',
        'copy-to'    : '',
    }
