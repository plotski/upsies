from .. import errors
from ..tools import mediainfo
from . import _base

import logging  # isort:skip
_log = logging.getLogger(__name__)


class MediainfoJob(_base.JobBase):
    name = 'mediainfo'
    label = 'Mediainfo'

    def initialize(self, content_path):
        self._content_path = content_path

    def execute(self):
        try:
            mi = mediainfo.as_string(self._content_path)
        except errors.MediainfoError as e:
            self.error(e)
        else:
            self.send(mi)
        finally:
            self.finish()
