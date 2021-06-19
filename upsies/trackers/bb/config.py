"""
Concrete :class:`~.base.TrackerConfigBase` subclass for bB
"""

import base64

from ...utils import imghosts, types
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
