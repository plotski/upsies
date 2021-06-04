import base64

import pytest

from upsies.trackers.bb import BbTrackerConfig


def test_defaults():
    assert BbTrackerConfig() == {
        'base_url'    : base64.b64decode('aHR0cHM6Ly9iYWNvbmJpdHMub3Jn').decode('ascii'),
        'username'    : '',
        'password'    : '',
        'source'      : 'bB',
        'image_host'  : 'imgbox',
        'screenshots' : 2,
        'add-to'      : '',
        'copy-to'     : '',
        'exclude'     : [
            r'\.(?i:nfo|txt|jpg|jpeg|png|sfv|md5)$',
            r'/(?i:sample|extra|bonus|feature)',
        ],
    }


def test_screenshots_option():
    config = BbTrackerConfig()
    with pytest.raises(ValueError, match=r'^Minimum is 2$'):
        type(config['screenshots'])(1)
    with pytest.raises(ValueError, match=r'^Maximum is 10$'):
        type(config['screenshots'])(11)
