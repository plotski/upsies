"""
Low-level wrappers and helpers
"""

import collections
import importlib
import itertools
import types


# https://github.com/tensorflow/tensorflow/blob/master/tensorflow/python/util/lazy_loader.py
class LazyModule(types.ModuleType):
    """
    Lazily import module to decrease execution time

    :param str module: Name of the module
    :param mapping namespace: Usually the return value of `globals()`
    :param str name: Name of the module in `namespace`; defaults to `module`
    """

    def __init__(self, module, namespace, name=None):
        self._module = module
        self._namespace = namespace
        self._name = name or module
        super().__init__(module)

    def _load(self):
        # Import the target module and insert it into the parent's namespace
        module = importlib.import_module(self.__name__)
        self._namespace[self._name] = module

        # Update this object's dict so that if someone keeps a reference to the
        # LazyLoader, lookups are efficient (__getattr__ is only called on
        # lookups that fail).
        self.__dict__.update(module.__dict__)

        return module

    def __getattr__(self, item):
        module = self._load()
        return getattr(module, item)

    def __dir__(self):
        module = self._load()
        return dir(module)


def closest_number(n, ns):
    """Return the number from `ns` that is closest to `n`"""
    # https://stackoverflow.com/a/12141207
    return min(ns, key=lambda x: abs(x - n))


_byte_units = {
    'PiB': 1024 ** 5,
    'TiB': 1024 ** 4,
    'GiB': 1024 ** 3,
    'MiB': 1024 ** 2,
    'KiB': 1024,
}

def pretty_bytes(b):
    '''Return `b` as human-readable bytes, e.g. "24.3 MiB"'''
    for unit, bytes in _byte_units.items():
        if b >= bytes:
            return f'{b / bytes:.2f} {unit}'
    return f'{int(b)} B'


class CaseInsensitiveString(str):
    """String that ignores case when compared or sorted"""

    def __hash__(self):
        return hash(self.casefold())

    def __eq__(self, other):
        if not isinstance(other, str):
            return NotImplemented
        else:
            return self.casefold() == other.casefold()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.casefold() < other.casefold()

    def __le__(self, other):
        return self.casefold() <= other.casefold()

    def __gt__(self, other):
        return self.casefold() > other.casefold()

    def __ge__(self, other):
        return self.casefold() >= other.casefold()


def is_sequence(obj):
    """Return whether `obj` is a sequence and not a string"""
    return (isinstance(obj, collections.abc.Sequence)
            and not isinstance(obj, str))


def merge_dicts(a, b, path=()):
    """Merge nested dictionaries `a` and `b` into a new dictionary"""
    keys = itertools.chain(a, b)
    merged = {}
    for key in keys:
        if isinstance(a.get(key), dict) and isinstance(b.get(key), dict):
            merged[key] = merge_dicts(a[key], b[key], path + (key,))
        elif key in b:
            # Value from b takes precedence
            merged[key] = b[key]
        elif key in a:
            # Value from a is default
            merged[key] = a[key]
    return merged


# Provide submodules; allow submodules to import stuff from __init__
from . import (browser, cache, country, daemon, fs, guessit, html, http,
               signal, subproc, timestamp, video)
