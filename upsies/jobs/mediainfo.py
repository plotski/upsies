"""
Wrapper for ``mediainfo`` command
"""

import asyncio

from .. import errors
from ..utils import fs, video
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class MediainfoJob(JobBase):
    """
    Get output from ``mediainfo`` command

    See :func:`.utils.video.mediainfo` for more information.
    """

    name = 'mediainfo'
    label = 'Mediainfo'

    # Don't show mediainfo output in TUI. It is printed out to stdout if this is
    # the only/final job.
    hidden = True

    @property
    def cache_id(self):
        """Final segment of `content_path`"""
        return fs.basename(self._content_path)

    def initialize(self, *, content_path):
        """
        Set internal state

        :param content_path: Path to video file or directory that contains a
            video file
        """
        self._content_path = content_path

    def execute(self):
        """Call ``mediainfo`` in an asynchronous thread"""
        self.add_task(
            coro=self._get_mediainfo(),
            finish_when_done=True,
        )

    async def _get_mediainfo(self):
        loop = asyncio.get_event_loop()
        try:
            mediainfo = await loop.run_in_executor(None, lambda: video.mediainfo(self._content_path))
        except errors.ContentError as e:
            self.error(e)
        else:
            self.send(mediainfo)
