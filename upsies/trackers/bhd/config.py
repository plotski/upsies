"""
Concrete :class:`~.base.TrackerConfigBase` subclass for BHD
"""

import base64

from ...utils import argtypes, configfiles, imghosts, types
from ..base import TrackerConfigBase


class BhdTrackerConfig(TrackerConfigBase):
    defaults = {
        'upload_url': base64.b64decode('aHR0cHM6Ly9iZXlvbmQtaGQubWUvYXBpL3VwbG9hZA==').decode('ascii'),
        'announce_url': configfiles.config_value(
            value=base64.b64decode('aHR0cHM6Ly9iZXlvbmQtaGQubWUvYW5ub3VuY2U=').decode('ascii'),
            description='The announce URL without the private passkey.',
        ),
        'announce_passkey': configfiles.config_value(
            value='',
            description=(
                'The private part of the announce URL.\n'
                'Get it from the website: My Security -> Passkey'
            ),
        ),
        'apikey': configfiles.config_value(
            value='',
            description=(
                'Your personal private API key.\n'
                'Get it from the website: My Security -> API key'
            ),
        ),
        'source': 'BHD',
        'anonymous': configfiles.config_value(
            value=types.Bool('no'),
            description='Whether your username is displayed on your uploads.',
        ),
        'draft': configfiles.config_value(
            value=types.Bool('no'),
            description=(
                'Whether your uploads are stashed under Torrents -> Drafts '
                'after the upload instead of going live.'
            ),
        ),
        'image_host': types.Choice('imgbox', options=(imghost.name for imghost in imghosts.imghosts())),
        'screenshots': configfiles.config_value(
            value=types.Integer(4, min=3, max=10),
            description='How many screenshots to make.',
        ),
        'exclude': [
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
