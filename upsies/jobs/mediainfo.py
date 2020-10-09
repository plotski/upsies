from .. import errors
from ..tools import mediainfo
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class MediainfoJob(JobBase):
    name = 'mediainfo'
    label = 'Mediainfo'

    # Don't show mediainfo in TUI
    quiet = True

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
