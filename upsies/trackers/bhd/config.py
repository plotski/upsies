"""
Concrete :class:`~.base.TrackerConfigBase` subclass for BHD
"""

import base64

from ...utils import imghosts, types
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
            r'\.(?i:nfo|txt|jpg|jpeg|png|sfv|md5)$',
            r'/(?i:sample)',
        ],
    }
