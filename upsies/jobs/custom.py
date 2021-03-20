"""
Custom job that provide the result of a coroutine
"""

import asyncio

from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class CustomJob(JobBase):
    """Wrapper around coroutine function or awaitable"""

    @property
    def name(self):
        return self._name

    @property
    def label(self):
        return self._label

    def initialize(self, *, name, label, worker):
        """
        Set internal state

        :param name: Name for internal use
        :param label: Name for user-facing use
        :param worker: Coroutine function (a function defined with an
            ``async def`` syntax) that takes the job instance as a
            positional argument.

        This job finishes when `worker` returns.

        :class:`~.asyncio.CancelledError` from `worker` is ignored. Any other
        exceptions are passed to :meth:`~.JobBase.exception`.
        """
        self._name = str(name)
        self._label = str(label)
        self._worker = worker
        self._task = None

    def execute(self):
        self._task = asyncio.ensure_future(
            self._catch_cancelled_error(
                self._worker(self),
            ),
        )
        self._task.add_done_callback(self._handle_worker_done)

    async def _catch_cancelled_error(self, worker):
        try:
            return await worker
        except asyncio.CancelledError:
            _log.debug('%s: Cancelled: %r', self.name, worker)

    def _handle_worker_done(self, task):
        try:
            result = task.result()
        except BaseException as e:
            self.exception(e)
        else:
            if result:
                self.send(result)
        finally:
            self.finish()

    async def wait(self):
        """Wait for `worker`"""
        if self._task:
            await self._task
        await super().wait()

    def finish(self):
        """Cancel `worker` and finish this job"""
        if self._task:
            self._task.cancel()
        super().finish()
