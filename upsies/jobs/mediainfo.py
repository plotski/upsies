import asyncio

from .. import errors
from ..tools import mediainfo
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class MediainfoJob(JobBase):
    name = 'mediainfo'
    label = 'Mediainfo'

    # Don't show mediainfo output in UI
    hidden = True

    def initialize(self, content_path):
        self._content_path = content_path

    def execute(self):
        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(None, lambda: mediainfo.as_string(self._content_path))
        fut.add_done_callback(self.handle_output)

    def handle_output(self, fut):
        try:
            mi = fut.result()
        except errors.MediainfoError as e:
            self.error(e)
        else:
            self.send(mi)
        finally:
            self.finish()
