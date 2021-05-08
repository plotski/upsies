import asyncio
import itertools

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Throbber:
    """
    Provide alternating activity indicator string to callback at fixed intervals

    :param callable callback: Callable that receives a single string from
        `states` as a positional argument
    :param states: Sequence of strings that are cycled through and passed to
        `callback` individually
    :param float interval: Delay between calls to `callback`
    :param bool active: Whether the throbber is throbbing right away
    """

    def __init__(self, *, callback=None, states=('⠷', '⠯', '⠟', '⠻', '⠽', '⠾'),
                 interval=0.1, active=False):
        self._iterator = itertools.cycle(states)
        self._interval = float(interval)
        self._callback = callback or None
        self.active = active

    @property
    def active(self):
        """Whether `callback` being called continuously"""
        return getattr(self, '_active', False)

    @active.setter
    def active(self, active):
        if active:
            if not getattr(self, '_active', None):
                self._active = True
                self._iterate()
        else:
            self._active = False

    @property
    def next_state(self):
        return next(self._iterator)

    def _iterate(self):
        if self.active:
            if self._callback:
                self._callback(self.next_state)
            asyncio.get_event_loop().call_later(self._interval, self._iterate)
