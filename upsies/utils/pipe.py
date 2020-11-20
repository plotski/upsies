import collections

from ..jobs import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Pipe:
    """
    Connect one job's output to another job's :meth:`~JobBase.pipe_input`

    When `sender` is finished, :meth:`pipe_closed` is called on `receiver`'s
    object.

    .. note:: It's not necessary to keep a reference to a :class:`Pipe` instance
              because `sender` references it as a callback and thus keeps it
              from getting garbage-collected..

    :param sender: Job to get output from
    :type sender: :class:`JobBase` child class instance
    :param receiver: Job to send output to
    :type receiver: :class:`JobBase` instance with a :meth:`~JobBase.pipe_input`
        method
    """

    def __init__(self, sender, receiver):
        if not isinstance(sender, JobBase):
            raise TypeError(f'Not a JobBase instance: {sender!r}')
        if not isinstance(receiver, JobBase):
            raise TypeError(f'Not a JobBase instance: {receiver!r}')

        self._sender = sender
        self._receiver = receiver
        self._sender_output_cache = collections.deque()
        self._sender.signal.register('output', self._handle_sender_output)
        self._sender.signal.register('finished', self._handle_sender_finished)
        self._is_closed = False

    def _handle_sender_output(self, output):
        self._sender_output_cache.append(output)
        self._flush()

    def _handle_sender_finished(self, sender):
        self._sender_output_cache.append(None)
        self._flush()

    def _flush(self):
        while self._sender_output_cache:
            output = self._sender_output_cache.popleft()
            if output is None:
                self._is_closed = True
                self._receiver.pipe_closed()
            elif self._is_closed:
                raise RuntimeError('Output received on closed pipe')
            else:
                self._receiver.pipe_input(output)
