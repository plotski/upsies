"""
Managing callbacks
"""

import collections
import contextlib

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Signal:
    """Simple callback registry"""

    def __init__(self, *signals):
        self._signals = {}
        self._suspended_signals = set()
        self._emissions = []
        self._record_signals = []
        for signal in signals:
            self.add(signal)

    def add(self, signal, record=False):
        """
        Create new `signal`

        :param hashable signal: Any hashable object
        :param bool record: Whether emissions of this signal are recorded in
            :attr:`emissions`

        :raise TypeError: if `signal` is not hashable
        :raise RuntimeError: if `signal` has been added previously
        """
        if not isinstance(signal, collections.abc.Hashable):
            raise TypeError(f'Unhashable signal: {signal!r}')
        elif signal in self._signals:
            raise RuntimeError(f'Signal already added: {signal!r}')
        else:
            self._signals[signal] = []
            if record:
                self.record(signal)

    @property
    def signals(self):
        """Mutable dictionary of signals mapped to a lists of callbacks"""
        return self._signals

    def record(self, signal):
        """Record emissions of `signal` in :attr:`emissions`"""
        if signal not in self._signals:
            raise ValueError(f'Unknown signal: {signal!r}')
        else:
            self._record_signals.append(signal)

    @property
    def recording(self):
        """class:`list` of signals that are recorded"""
        return self._record_signals

    def register(self, signal, callback):
        """
        Call `callback` when `signal` is emited

        :param hashable signal: Previously added signal
        :param callable callback: Any callback. The signature depends on the caller of
            :meth:`emit`.

        :raise ValueError: if `signal` was not added first
        :raise TypeError: if `callback` is not callable
        """
        if signal not in self._signals:
            raise ValueError(f'Unknown signal: {signal!r}')
        elif not callable(callback):
            raise TypeError(f'Not a callable: {callback!r}')
        else:
            self._signals[signal].append(callback)

    def emit(self, signal, *args, **kwargs):
        """
        Call callbacks that are registered to `signal`

        :param hashable signal: Previously added signal

        Any other arguments are passed on to the callbacks.
        """
        if signal not in self._suspended_signals:
            for callback in self._signals[signal]:
                callback(*args, **kwargs)
            if signal in self._record_signals:
                self._emissions.append((signal, {'args': args, 'kwargs': kwargs}))

    @property
    def emissions(self):
        """
        Sequence of recorded :meth:`emit` calls

        Each call is stored as a tuple like this::

            (<signal>, {"args": <positional arguments>,
                        "kwargs": <keyword arguments>})
        """
        return tuple(self._emissions)

    def replay(self, emissions):
        """:meth:`emit` previously recorded :attr:`emissions`"""
        for signal, payload in emissions:
            self.emit(signal, *payload['args'], **payload['kwargs'])

    @contextlib.contextmanager
    def suspend(self, *signals):
        """
        Context manager that blocks certain signals in its body

        :param signals: Which signals to block

        :raise ValueError: if any signal in `signals` is not registered
        """
        for signal in signals:
            if signal not in self._signals:
                raise ValueError(f'Unknown signal: {signal!r}')

        self._suspended_signals.update(signals)

        try:
            yield
        finally:
            self._suspended_signals.difference_update(signals)
