import asyncio
import enum

from .. import errors
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubmitJob(JobBase):
    """
    Submit torrent file and other metadata to tracker

    :param tracker: :class:`Tracker` instance from one of the submodules of
        :mod:`~trackers`
    """

    name = 'submit'
    label = 'Submit'

    @property
    def cache_file(self):
        return None

    def initialize(self, tracker):
        self._tracker = tracker
        self._submit_lock = asyncio.Lock()
        self._callbacks = {
            self.signal.logging_in: [],
            self.signal.logged_in: [],
            self.signal.uploading: [],
            self.signal.uploaded: [],
            self.signal.logging_out: [],
            self.signal.logged_out: [],
        }

    async def wait(self):
        async with self._submit_lock:
            if not self.is_finished:
                _log.debug('Waiting for jobs before upload: %r', self._tracker.jobs_before_upload)
                await asyncio.gather(*(job.wait() for job in self._tracker.jobs_before_upload))

                names = [job.name for job in self._tracker.jobs_before_upload]
                outputs = [job.output for job in self._tracker.jobs_before_upload]
                metadata = dict(zip(names, outputs))
                await self._submit(metadata)
                self.finish()

    async def _submit(self, metadata):
        _log.debug('%s: Submitting %s', self._tracker.name, metadata.get('create-torrent'))
        try:
            self._call_callbacks(self.signal.logging_in)
            await self._tracker.login()
            self._call_callbacks(self.signal.logged_in)
            try:
                self._call_callbacks(self.signal.uploading)
                torrent_page_url = await self._tracker.upload(metadata)
                self.send(torrent_page_url)
                self._call_callbacks(self.signal.uploaded)
            finally:
                self._call_callbacks(self.signal.logging_out)
                await self._tracker.logout()
                self._call_callbacks(self.signal.logged_out)
        except errors.RequestError as e:
            self.error(e)

    def execute(self):
        pass

    class signal(enum.Enum):
        logging_in = 1
        logged_in = 2
        uploading = 3
        uploaded = 4
        logging_out = 5
        logged_out = 6

    def on(self, signal, callback):
        """
        Run `callback` when `signal` happens

        :param signal: When to call `callback`
        :type signal: Any attribute of :attr:`signal`
        :param callable callback: Callable that doesn't take any arguments
        """
        if not isinstance(signal, self.signal):
            raise RuntimeError(f'Unknown signal: {signal!r}')
        else:
            self._callbacks[signal].append(callback)

    def _call_callbacks(self, signal):
        for cb in self._callbacks[signal]:
            cb()
