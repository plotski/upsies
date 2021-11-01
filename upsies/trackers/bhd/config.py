"""
Concrete :class:`~.base.TrackerConfigBase` subclass for BHD
"""

import base64

from ...utils import argtypes, imghosts, types
from ..base import TrackerConfigBase


class BhdTrackerConfig(TrackerConfigBase):
    defaults = {
        'upload_url'       : base64.b64decode('aHR0cHM6Ly9iZXlvbmQtaGQubWUvYXBpL3VwbG9hZA==').decode('ascii'),
        'announce_url'     : base64.b64decode('aHR0cHM6Ly90cmFja2VyLmJleW9uZC1oZC5tZToyMDUzL2Fubm91bmNl').decode('ascii'),
        'announce_passkey' : '',
        'apikey'           : '',
        'source'           : 'BHD',
        'anonymous'        : types.Bool('no'),
        'draft'            : types.Bool('no'),
        'image_host'       : types.Choice('imgbox', options=(imghost.name for imghost in imghosts.imghosts())),
        'screenshots'      : types.Integer(4, min=3, max=10),
        'exclude'          : [
            r'\.(?i:txt|jpg|jpeg|png|sfv|md5)$',
            r'/(?i:sample)',
        ],
    }

    argument_definitions = {
        'submit': {
            ('--custom-edition', '--ce'): {
                'help': 'Non-standard edition, e.g. "Final Cut"',
                'default': '',
            },
            ('--draft', '--dr'): {
                'help': 'Upload as draft',
                'action': 'store_true',
                # The default value must be None so CommandBase.get_options()
                # doesn't always overwrite the value with the config file value.
                'default': None,
            },
            ('--personal-rip', '--pr'): {
                'help': 'Tag as your own encode',
                'action': 'store_true',
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
            ('--special', '--sp'): {
                'help': 'Tag as special episode, e.g. Christmas special (ignored for movie uploads)',
                'action': 'store_true',
            },
            ('--only-description', '--od'): {
                'help': 'Only generate description (do not upload anything)',
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
