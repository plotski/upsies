import itertools
import sys

from ... import utils

import logging  # isort:skip
_log = logging.getLogger(__name__)


def is_tty():
    """Whether we live in a terminal and can interacte with the user"""
    # As long as we have input and output, we have user interaction. sys.stdout
    # may be redirected, but prompt-toolkit will print to sys.stderr instead.
    if not sys.stdin or (not sys.stdout and not sys.stderr):
        return False
    else:
        if sys.stdin.isatty():
            if sys.stdout and sys.stdout.isatty():
                return True
            elif sys.stderr and sys.stderr.isatty():
                return True
        return False


class ActivityIndicator:
    """
    Provide alternating activity indicator string to callback at fixed intervals

    :param callable callback: Callable that receives a single string from
        `states` as a positional argument
    :param states: Sequence of strings that are cycled through and passed to
        `callback` individually
    :param float interval: Delay between calls to `callback`
    :param bool active: Whether `callback` is called right away
    :param str format: Format string to embedd the activity indicator in;
        ``{indicator}`` is replaced with one of the `states`
    """

    def __init__(self, *, callback=None, states=('⠷', '⠯', '⠟', '⠻', '⠽', '⠾'),
                 interval=0.25, active=False, format='{indicator}'):
        self._iterator = itertools.cycle(states)
        self._interval = float(interval)
        self._callback = callback or None
        self._format = format
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
        return self._format.format(indicator=next(self._iterator))

    def _iterate(self):
        if self.active:
            if self._callback:
                self._callback(self.next_state)
            utils.get_aioloop().call_later(self._interval, self._iterate)
