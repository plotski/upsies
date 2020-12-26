from . import trackers

defaults = {
    'trackers': {
        'dummy': trackers.dummy.DummyTrackerConfig(),
        'nbl': trackers.nbl.NblTrackerConfig(),
    },

    'imghosts': {
        'dummy': {},
        'imgbox': {},
    },

    'clients': {
        'dummy': {},
        'transmission': {
            'url': 'http://localhost:9091/transmission/rpc',
            'username': '',
            'password': '',
        },
    },
}
"""Defaults for configuration options"""
