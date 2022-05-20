import base64

from upsies.trackers.nbl import NblTrackerConfig


def test_defaults():
    assert NblTrackerConfig() == {
        'upload_url'   : base64.b64decode('aHR0cHM6Ly9uZWJ1bGFuY2UuaW8vdXBsb2FkLnBocA==').decode('ascii'),
        'announce_url' : '',
        'apikey'       : '',
        'source'       : 'NBL',
        'exclude'      : [],
        'add_to'       : '',
        'copy_to'      : '',
    }


def test_argument_definitions():
    assert NblTrackerConfig.argument_definitions == {
    }
