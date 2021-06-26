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
    rel_path = __package__.replace('.', os.sep)
    assert own_path.endswith(rel_path), f'{own_path!r}.endswith({rel_path!r})'
    project_path = own_path[:-len(rel_path)]

    # Add relative path within project to given package
    package_path = os.path.join(project_path, package.replace('.', os.sep))

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


class MonitoredList(collections.abc.MutableSequence):
    """
    :class:`list` that calls `callback` after every change

    :param callback: Callable that gets the instance as a positional argument
    """

    def __init__(self, *args, callback, **kwargs):
        self._list = list(*args, **kwargs)
        self._callback = callback

    def __getitem__(self, index):
        return self._list[index]

    def __setitem__(self, index, value):
        self._list[index] = value
        self._callback(self)

    def __delitem__(self, index):
        del self._list[index]
        self._callback(self)

    def insert(self, index, value):
        self._list.insert(index, value)
        self._callback(self)

    def __len__(self):
        return len(self._list)

    def __eq__(self, other):
        return self._list == other

    def __repr__(self):
        return f'{type(self).__name__}({repr(self._list)}, callback={self._callback!r})'


class RestrictedMapping(collections.abc.MutableMapping):
    """
    :class:`dict` that only accepts the keys provided when it was instantiated

    >>> d = RestrictedMapping({'foo': 'bar'})
    >>> d['foo']
    >>> 'bar'
    >>> d['baz']
    >>> KeyError: 'baz'

    >>> d = RestrictedMapping(allowed_keys=('foo', 'bar'), foo=1, bar=2)
    >>> d['foo']
    >>> 1
    >>> d['baz']
    >>> KeyError: 'baz'
    """

    def __init__(self, *args, allowed_keys=(), **kwargs):
        self._allowed_keys = set(allowed_keys)
        if len(args) == 1 and isinstance(args[0], collections.abc.Mapping):
            self._allowed_keys.update(args[0])
            self._dict = dict(args[0])
        else:
            self._dict = dict(*args, **kwargs)

    def __getitem__(self, key):
        return self._dict[key]

    def __setitem__(self, key, value):
        if key in self._allowed_keys:
            self._dict[key] = value
        else:
           raise KeyError(key)

    def __delitem__(self, key):
        del self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __repr__(self):
        return repr(self._dict)


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
        if (isinstance(a.get(key), collections.abc.Mapping) and
            isinstance(b.get(key), collections.abc.Mapping)):
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


def as_groups(sequence, group_sizes, default=None):
    """
    Iterate over items from `iterable` in evenly sized groups

    :params sequence: List of items to group
    :params group_sizes: Sequence of group sizes; the one with the lowest number
        of `default` items in the last group is picked automatically
    :param default: Value to pad last group with if
        ``len(iterable) % group_size != 0``
    """
    # Calculate group size that results in the least number of `default` values
    # in the final group
    gs_map = collections.defaultdict(lambda: [])
    for gs in group_sizes:
        # How many items from `iterable` are in the last group
        overhang = len(sequence) % gs
        # How many `default` values are in the last group
        default_count = 0 if overhang == 0 else gs - overhang
        gs_map[default_count].append(gs)

    lowest_default_count = sorted(gs_map)[0]
    group_size = max(gs_map[lowest_default_count])
    args = [iter(sequence)] * group_size
    yield from itertools.zip_longest(*args, fillvalue=default)


from . import (argtypes, browser, btclients, configfiles, daemon, fs, html,
               http, image, imghosts, iso, release, scene, signal, string,
               subproc, timestamp, torrent, types, video, webdbs)
