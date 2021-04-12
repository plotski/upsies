"""
Swiss Army knife
"""

import collections
import importlib
import inspect
import itertools
import os
import types as _types


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


# https://github.com/tensorflow/tensorflow/blob/master/tensorflow/python/util/lazy_loader.py
class LazyModule(_types.ModuleType):
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
            if '.' not in name:
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
    subclses = set()
    for mod in modules:
        for name, member in inspect.getmembers(mod):
            if (member is not basecls and
                isinstance(member, type) and
                issubclass(member, basecls)):
                subclses.add(member)
    return subclses


def closest_number(n, ns, max=None, default=0):
    """
    Return the number from `ns` that is closest to `n`

    :param n: Given number
    :param ns: Sequence of allowed numbers
    :param max: Remove any item from `ns` that is larger than `max`
    :param default: Return value in case `ns` is empty
    """
    if max is not None:
        ns_ = tuple(n_ for n_ in ns if n_ <= max)
        if not ns_:
            raise ValueError(f'No number equal to or below {max}: {ns}')
    else:
        ns_ = ns
    return min(ns_, key=lambda x: abs(x - n), default=default)


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


def deduplicate(l, key=None):
    """
    Return sequence `l` with all duplicate items removed while maintaining the
    original order

    :param key: Callable that gets each item and returns a hashable identifier
        for that item
    """
    if key is None:
        key = lambda k: k
    seen_keys = set()
    deduped = []
    for item in l:
        k = key(item)
        if k not in seen_keys:
            seen_keys.add(k)
            deduped.append(item)
    return deduped


from . import (browser, btclients, configfiles, daemon, fs, html, http, image,
               imghosts, iso, release, scene, signal, string, subproc,
               timestamp, torrent, types, video, webdbs)
