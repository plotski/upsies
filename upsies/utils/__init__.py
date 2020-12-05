"""
Low-level wrappers and helpers
"""

import collections
import importlib
import inspect
import itertools
import os
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


def submodules(package):
    """
    Return list of submodules and subpackages in `package`

    :param str package: Qualified name of parent package,
        e.g. "upsies.tools.btclient"
    """
    # Get absolute path to parent directory of top-level package
    own_path = os.path.dirname(__file__)
    rel_path = __package__.replace('.', '/')
    assert own_path.endswith(rel_path)
    project_path = own_path[:-len(rel_path)]

    # Add path to given package
    package_path = os.path.join(project_path, package.replace('.', '/'))

    # Find and import public submodules
    submods = []
    for name in os.listdir(package_path):
        if not name.startswith('_') and name.endswith('.py'):
            modname = name[:-3]  # Remove .py
            submods.append(
                importlib.import_module(name=f'.{modname}', package=package)
            )
    return submods


def subclasses(basecls, modules):
    """
    Return list of subclasses

    :param type basecls: Class that all returned classes are a subclass of
    :param modules: List of modules to search
    """
    subclses = []
    for mod in modules:
        for name, member in inspect.getmembers(mod):
            if (member is not basecls and
                isinstance(member, type) and
                issubclass(member, basecls)):
                subclses.append(member)
    return subclses


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
from . import (browser, cache, configfiles, country, daemon, fs, guessit, html,
               http, signal, subproc, timestamp, video)
