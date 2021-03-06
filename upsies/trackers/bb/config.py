"""
BbTrackerConfig class
"""

import base64

from ..base import TrackerConfigBase


class BbTrackerConfig(TrackerConfigBase):
    defaults = {
        'base_url'   : base64.b64decode('aHR0cHM6Ly9iYWNvbmJpdHMub3Jn').decode('ascii'),
        'username'   : '',
        'password'   : '',
        'exclude'    : [],
        'source'     : 'bB',
        'image_host' : 'imgbox',
    }
