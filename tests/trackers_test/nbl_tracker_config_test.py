import base64

from upsies.trackers.nbl import NblTrackerConfig


def test_defaults():
    assert NblTrackerConfig() == {
        'base_url'   : base64.b64decode('aHR0cHM6Ly9uZWJ1bGFuY2UuaW8=').decode('ascii'),
        'username'   : '',
        'password'   : '',
        'announce'   : '',
        'exclude'    : [],
        'source'     : 'NBL',
        'image_host' : '',
        'add-to'     : '',
    }
