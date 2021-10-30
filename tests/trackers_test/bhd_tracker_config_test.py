import base64

import pytest

from upsies.trackers.bhd import BhdTrackerConfig
from upsies.utils import argtypes, imghosts, types


def test_defaults():
    assert BhdTrackerConfig() == {
        'upload_url'       : base64.b64decode('aHR0cHM6Ly9iZXlvbmQtaGQubWUvYXBpL3VwbG9hZA==').decode('ascii'),
        'announce_url'     : base64.b64decode('aHR0cHM6Ly90cmFja2VyLmJleW9uZC1oZC5tZToyMDUzL2Fubm91bmNl').decode('ascii'),
        'announce_passkey' : '',
        'apikey'           : '',
        'source'           : 'BHD',
        'anonymous'        : types.Bool('no'),
        'draft'            : types.Bool('no'),
        'image_host'       : 'imgbox',
        'add-to'           : '',
        'screenshots'      : 4,
        'copy-to'          : '',
        'exclude'          : [
            r'\.(?i:txt|jpg|jpeg|png|sfv|md5)$',
            r'/(?i:sample)',
        ],
    }


def test_argument_definitions():
    assert BhdTrackerConfig.argument_definitions == {
        'submit': {
            ('--screenshots', '--ss'): {
                'help': ('How many screenshots to make '
                         f'(min={BhdTrackerConfig.defaults["screenshots"].min}, '
                         f'max={BhdTrackerConfig.defaults["screenshots"].max})'),
                'type': argtypes.number_of_screenshots(
                    min=BhdTrackerConfig.defaults['screenshots'].min,
                    max=BhdTrackerConfig.defaults['screenshots'].max,
                ),
            },
            ('--custom-edition', '--ce'): {
                'help': 'Non-standard edition, e.g. "Final Cut"',
                'default': '',
            },
            ('--draft', '--dr'): {
                'help': 'Upload as draft',
                'action': 'store_true',
                'default': None,
            },
            ('--personal-rip', '--pr'): {
                'help': 'Tag as your own encode',
                'action': 'store_true',
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


def test_screenshots_option():
    config = BhdTrackerConfig()
    with pytest.raises(ValueError, match=r'^Minimum is 3$'):
        type(config['screenshots'])(2)
    with pytest.raises(ValueError, match=r'^Maximum is 10$'):
        type(config['screenshots'])(11)


def test_image_host_option():
    config = BhdTrackerConfig()
    imghost_names = ', '.join(imghost.name for imghost in imghosts.imghosts())

    with pytest.raises(ValueError, match=rf'^Not one of {imghost_names}: foo$'):
        type(config['image_host'])('foo')

    imghost = type(config['image_host'])('dummy')
    with pytest.raises(ValueError, match=rf'^Not one of {imghost_names}: foo$'):
        type(imghost)('foo')
