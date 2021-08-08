import base64

import pytest

from upsies.trackers.bhd import BhdTrackerConfig
from upsies.utils import btclients, imghosts, types


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
        'add-to'     : types.Choice(
            '',
            empty_ok=True,
            options=(client.name for client in btclients.clients()),
        ),
        'copy-to'          : '',
        'exclude'          : [
            r'\.(?i:nfo|txt|jpg|jpeg|png|sfv|md5)$',
            r'/(?i:sample)',
        ],
    }


def test_image_host_option():
    config = BhdTrackerConfig()
    imghost_names = ', '.join(imghost.name for imghost in imghosts.imghosts())

    with pytest.raises(ValueError, match=rf'^Not one of {imghost_names}: foo$'):
        type(config['image_host'])('foo')

    imghost = type(config['image_host'])('dummy')
    with pytest.raises(ValueError, match=rf'^Not one of {imghost_names}: foo$'):
        type(imghost)('foo')
