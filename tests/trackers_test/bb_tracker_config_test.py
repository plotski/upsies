import base64

import pytest

from upsies import utils
from upsies.trackers.bb import BbTrackerConfig
from upsies.utils import imghosts


def test_defaults():
    assert BbTrackerConfig() == {
        'base_url'    : base64.b64decode('aHR0cHM6Ly9iYWNvbmJpdHMub3Jn').decode('ascii'),
        'username'    : '',
        'password'    : '',
        'source'      : 'bB',
        'image_host'  : 'imgbox',
        'screenshots' : 2,
        'add-to'      : '',
        'copy-to'     : '',
        'exclude'     : [
            r'\.(?i:nfo|txt|jpg|jpeg|png|sfv|md5)$',
            r'/(?i:sample|extra|bonus|feature)',
        ],
    }


def test_argument_definitions():
    assert BbTrackerConfig.argument_definitions == {
        'submit': {
            ('--screenshots', '--ss'): {
                'help': ('How many screenshots to make '
                         f'(min={BbTrackerConfig.defaults["screenshots"].min}, '
                         f'max={BbTrackerConfig.defaults["screenshots"].max})'),
                'type': utils.argtypes.number_of_screenshots(
                    min=BbTrackerConfig.defaults['screenshots'].min,
                    max=BbTrackerConfig.defaults['screenshots'].max,
                ),
            },
            ('--poster-file', '--pf'): {
                'help': 'Path or URL to poster image',
            },
            ('--anime', '--an'): {
                'help': 'Tag upload as anime (ignored for movies)',
                'action': 'store_true',
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


def test_screenshots_option():
    config = BbTrackerConfig()
    with pytest.raises(ValueError, match=r'^Minimum is 2$'):
        type(config['screenshots'])(1)
    with pytest.raises(ValueError, match=r'^Maximum is 10$'):
        type(config['screenshots'])(11)


def test_image_host_option():
    config = BbTrackerConfig()
    imghost_names = ', '.join(imghost.name for imghost in imghosts.imghosts())

    with pytest.raises(ValueError, match=rf'^Not one of {imghost_names}: foo$'):
        type(config['image_host'])('foo')

    imghost = type(config['image_host'])('dummy')
    with pytest.raises(ValueError, match=rf'^Not one of {imghost_names}: foo$'):
        type(imghost)('foo')
