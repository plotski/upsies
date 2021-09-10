import base64

from upsies.trackers.nbl import NblTrackerConfig


def test_defaults():
    assert NblTrackerConfig() == {
        'base_url'   : base64.b64decode('aHR0cHM6Ly9uZWJ1bGFuY2UuaW8=').decode('ascii'),
        'username'   : '',
        'password'   : '',
        'exclude'    : [],
        'source'     : 'NBL',
        'image_host' : '',
        'add-to'     : '',
        'copy-to'    : '',
    }


def test_argument_definitions():
    assert NblTrackerConfig.argument_definitions == {
        ('--ignore-dupes', '-D'): {
            'help': 'Force submission even if the tracker reports duplicates',
            'action': 'store_true',
        },
    }
