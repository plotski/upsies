"""
Managing callbacks
"""

import collections


class Signal:
    """Simple callback registry"""

    def __init__(self, *signals):
        self._signals = {}
        for signal in signals:
            self.add(signal)

    def add(self, signal):
        """
        Create new `signal`

        :param hashable signal: Any hashable object

        :raise TypeError: if `signal` is not hashable
        :raise RuntimeError: if `signal` has been added previously
        """
        if not isinstance(signal, collections.abc.Hashable):
            raise TypeError(f'Unhashable signal: {signal!r}')
        elif signal in self._signals:
            raise RuntimeError(f'Signal already added: {signal!r}')
        else:
            self._signals[signal] = []

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
        for callback in self._signals[str(signal)]:
            callback(*args, **kwargs)

    @property
    def signals(self):
        """Mutable dictionary of signals mapped to a lists of callbacks"""
        return self._signals
