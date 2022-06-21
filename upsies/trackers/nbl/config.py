"""
Concrete :class:`~.base.TrackerConfigBase` subclass for NBL
"""

import base64

from ...utils import configfiles
from .. import base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class NblTrackerConfig(base.TrackerConfigBase):
    defaults = {
        'upload_url': base64.b64decode('aHR0cHM6Ly9uZWJ1bGFuY2UuaW8vdXBsb2FkLnBocA==').decode('ascii'),
        'announce_url': configfiles.config_value(
            value='',
            description=(
                'The complete announce URL with your private passkey.\n'
                'Get it from the website: Shows -> Upload -> Your personal announce URL'
            ),
        ),
        'apikey': configfiles.config_value(
            value='',
            description=(
                'Your personal private API key.\n'
                'Get it from the website: <USERNAME> -> Settings -> API keys'
            ),
        ),
        'source': 'NBL',
        'exclude': [],
    }

    argument_definitions = {
        # Custom arguments, e.g. "upsies submit nbl --foo bar"
    }
