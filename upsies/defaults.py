from . import trackers

defaults = {
    'trackers': {
        tracker.name: tracker.TrackerConfig()
        for tracker in trackers.trackers()
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
