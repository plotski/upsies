"""
Concrete :class:`~.base.TrackerConfigBase` subclass for bB
"""

import base64

from ...utils import argtypes, imghosts, types
from ..base import TrackerConfigBase


class BbTrackerConfig(TrackerConfigBase):
    defaults = {
        'base_url'    : base64.b64decode('aHR0cHM6Ly9iYWNvbmJpdHMub3Jn').decode('ascii'),
        'username'    : '',
        'password'    : '',
        'source'      : 'bB',
        'image_host'  : types.Choice('imgbox', options=(imghost.name for imghost in imghosts.imghosts())),
        'screenshots' : types.Integer(2, min=2, max=10),
        'exclude'     : [
            r'\.(?i:nfo|txt|jpg|jpeg|png|sfv|md5)$',
            r'/(?i:sample|extra|bonus|feature)',
        ],
    }

    argument_definitions = {
        'submit': {
            ('--screenshots', '--ss'): {
                'help': ('How many screenshots to make '
                         f'(min={defaults["screenshots"].min}, '
                         f'max={defaults["screenshots"].max})'),
                'type': argtypes.number_of_screenshots(
                    min=defaults['screenshots'].min,
                    max=defaults['screenshots'].max,
                ),
            },
            ('--poster-file', '--pf'): {
                'help': 'Path or URL to poster image',
            },
            ('--anime', '--an'): {
                'help': 'Tag upload as anime (ignored for movies)',
                'action': 'store_true',
            },
            ('--description', '--desc'): {
                'group': 'generate-metadata',
                'help': 'Only generate description',
                'action': 'store_true',
            },
            ('--poster', '-p'): {
                'group': 'generate-metadata',
                'help': 'Only generate poster URL',
                'action': 'store_true',
            },
            ('--release-info', '-i'): {
                'group': 'generate-metadata',
                'help': 'Only generate release info',
                'action': 'store_true',
            },
            ('--tags', '-g'): {
                'group': 'generate-metadata',
                'help': 'Only generate tags',
                'action': 'store_true',
            },
            ('--title', '-t'): {
                'group': 'generate-metadata',
                'help': 'Only generate title',
                'action': 'store_true',
            },
        },
    }
