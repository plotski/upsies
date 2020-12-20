"""
Swiss Army knife
"""

import collections
import enum
import importlib
import inspect
import itertools
import os
import types


def os_family():
    """
    Return "windows" or "unix"
    """
    return 'windows' if os.name == 'nt' else 'unix'


try:
    from functools import cached_property
except ImportError:
    import functools

    # https://github.com/jackmaney/lazy-property/
    class cached_property():
        """Property that replaces itself with its return value on first access"""

        def __init__(self, fget):
            self.fget = fget
            functools.update_wrapper(self, fget)
            self.fset = None

        def __get__(self, obj, cls):
            if obj is None:
                return self
            else:
                value = self.fget(obj)
                setattr(obj, self.fget.__name__, value)
                return value


class ReleaseType(enum.Enum):
    '''
    Enum with the values ``movie``, ``series``, ``season``, ``episode`` and
    ``unknown``

    Use ``season`` or ``episode`` if it matters, ``series`` otherwise.

    All values are truthy except for ``unknown``.
    '''

    movie = 'movie'
    series = 'series'
    season = 'season'
    episode = 'episode'
    unknown = 'unknown'

    def __bool__(self):
        return self is not self.unknown

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f'{type(self).__name__}.{self.value}'


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

    :param str package: Fully qualified name of parent package,
        e.g. "upsies.utils.btclients"
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
        if not name.startswith('_'):
            if name.endswith('.py'):
                name = name[:-3]
            submods.append(
                importlib.import_module(name=f'.{name}', package=package)
            )
    return submods


def subclasses(basecls, modules):
    """
    Find subclasses in modules

    :param type basecls: Class that all returned classes are a subclass of
    :param modules: Modules to search
    :type modules: list of module objects
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
    """
    Merge nested dictionaries `a` and `b` into new dictionary with same
    structure
    """
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


from . import (browser, btclients, configfiles, country, daemon, fs, html,
               http, imghosts, mediainfo, release_info, screenshot, signal,
               subproc, timestamp, torrent, video, webdbs)
