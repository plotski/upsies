import collections

from ..jobs import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Pipe:
    """
    Connect one job's output to another job's :meth:`~JobBase.pipe_input`

    When `sender` is finished, :meth:`pipe_closed` is called on `receiver`'s
    object.

    .. note:: :class:`Pipe` instances do not have to be assigned to variables
              because `sender` keeps references of them as callbacks.

    :param sender: Job to collect output from
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
        self._sender.on_output(self._handle_sender_output)
        self._sender.on_finished(self._handle_sender_finished)
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
