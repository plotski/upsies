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
            ('--anime', '--an'): {
                'help': 'Tag upload as anime (ignored for movies)',
                'action': 'store_true',
            },
            ('--poster', '--po'): {
                'help': 'Path or URL to poster image',
            },
            ('--screenshots', '--ss'): {
                'help': ('How many screenshots to make '
                         f'(min={defaults["screenshots"].min}, '
                         f'max={defaults["screenshots"].max})'),
                'type': argtypes.number_of_screenshots(
                    min=defaults['screenshots'].min,
                    max=defaults['screenshots'].max,
                ),
            },
            ('--only-description', '--od'): {
                'help': 'Only generate description (do not upload anything)',
                'action': 'store_true',
                'group': 'generate-metadata',
            },
            ('--only-poster', '--op'): {
                'help': 'Only generate poster URL (do not upload anything)',
                'action': 'store_true',
                'group': 'generate-metadata',
            },
            ('--only-release-info', '--or'): {
                'help': 'Only generate release info (do not upload anything)',
                'action': 'store_true',
                'group': 'generate-metadata',
            },
            ('--only-tags', '--ota'): {
                'help': 'Only generate tags (do not upload anything)',
                'action': 'store_true',
                'group': 'generate-metadata',
            },
            ('--only-title', '--oti'): {
                'help': 'Only generate title (do not upload anything)',
                'action': 'store_true',
                'group': 'generate-metadata',
            },
        },
    }
