"""
Configuration files
"""

import collections
import configparser
import copy
import os
from os.path import exists as _path_exists

from .. import errors, utils

import logging  # isort:skip
_log = logging.getLogger(__name__)


def _is_list(value):
    return isinstance(value, collections.abc.Iterable) and not isinstance(value, str)

def _any2list(value):
    return list(value) if _is_list(value) else str(value).split()

def _any2string(value):
    return ' '.join(str(v) for v in value) if _is_list(value) else str(value)


class ConfigFiles(collections.abc.MutableMapping):
    """
    Combine multiple INI-style configuration files into nested dictionaries

    Each top-level dictionary represents one INI file. It maps section names to
    subsections. Subsections (which are sections in the INI file) contain pairs
    of options and values.

    Sections, subsections and options can be accessed like dictionaries.

    >>> config["main"]["foo"]["bar"]
    "This is bar's value"
    >>> config["main"]["foo"]
    {'bar': "This is bar's value", 'baz': 'Another value'}
    >>> config["main"]["foo"]["bar"] = 'Zatoichi'

    For convenience, `"."` is used as a delimiter.

    >>> config["main.foo.bar"] = "Ichi"
    >>> config["main.foo.bar"]
    'Ichi'

    List values use ``"\\n  "`` (newline followed by two spaces) as separators
    between items.

    :param defaults: Nested directory structure as described above with
        default values
    :param files: Mapping of section names to file paths that are :meth:`read`
        during initialization
    """

    def __init__(self, defaults, ignore_missing=False, **files):
        self._defaults = copy.deepcopy(defaults)
        self._cfg = _ConfigDict(self._defaults, types=self._build_types())
        self._files = {}  # Map section names to file paths
        for section, filepath in files.items():
            self.read(section, filepath, ignore_missing=ignore_missing)

    def _build_types(self):
        def get_type(value):
            if _is_list(value):
                return _any2list
            else:
                def converter(v, cls=type(value)):
                    return cls(_any2string(v))
            return converter

        types = {}
        for section, subsections in self._defaults.items():
            types[section] = {}
            for subsection, options in subsections.items():
                types[section][subsection] = {}
                for option, value in options.items():
                    types[section][subsection][option] = get_type(value)
        return types

    @utils.cached_property
    def paths(self):
        """Sorted tuple of ``section.subsection.option`` paths"""

        def _get_paths(dct, parents=()):
            paths = []
            for k, v in dct.items():
                k_parents = parents + (k,)
                if isinstance(v, collections.abc.Mapping):
                    paths.extend(_get_paths(v, parents=k_parents))
                else:
                    paths.append('.'.join(str(k) for k in k_parents))
            return tuple(sorted(paths))

        return _get_paths(self._defaults)

    def read(self, section, filepath, ignore_missing=False):
        """
        Read `filepath` and make its contents available as `section`

        :raises ConfigError: if reading or parsing a file fails
        """
        if ignore_missing and not _path_exists(filepath):
            self._files[section] = filepath
        else:
            try:
                with open(filepath, 'r') as f:
                    string = f.read()
            except OSError as e:
                raise errors.ConfigError(f'{filepath}: {e.strerror}')
            else:
                cfg = self._parse(section, string, filepath)
                for subsection_name, subsection in cfg.items():
                    for option_name, option_value in subsection.items():
                        try:
                            self._set(section, subsection_name, option_name, option_value)
                        except errors.ConfigError as e:
                            raise errors.ConfigError(f'{filepath}: {e}')
                self._files[section] = filepath

    def _set(self, section, subsection, option, value):
        if section not in self._cfg:
            raise errors.ConfigError(f'{section}: Unknown section')
        elif subsection not in self._cfg[section]:
            raise errors.ConfigError(f'{section}.{subsection}: Unknown subsection')
        elif option not in self._cfg[section][subsection]:
            raise errors.ConfigError(f'{section}.{subsection}.{option}: Unknown option')
        else:
            try:
                self._cfg[section][subsection][option] = value
            except errors.ConfigError as e:
                raise errors.ConfigError(f'{section}.{subsection}.{option}: {e}')

    @staticmethod
    def _parse(section, string, filepath):
        cfg = configparser.ConfigParser(
            default_section=None,
            interpolation=None,
        )
        try:
            cfg.read_string(string, source=filepath)
        except configparser.MissingSectionHeaderError as e:
            raise errors.ConfigError(f'{filepath}: Line {e.lineno}: {e.line.strip()}: Option outside of section')
        except configparser.ParsingError as e:
            lineno, msg = e.errors[0]
            raise errors.ConfigError(f'{filepath}: Line {lineno}: {msg}: Invalid syntax')
        except configparser.DuplicateSectionError as e:
            raise errors.ConfigError(f'{filepath}: Line {e.lineno}: {e.section}: Duplicate section')
        except configparser.DuplicateOptionError as e:
            raise errors.ConfigError(f'{filepath}: Line {e.lineno}: {e.option}: Duplicate option')
        except configparser.Error as e:
            raise errors.ConfigError(f'{filepath}: {e}')
        else:
            # Make normal dictionary from ConfigParser instance
            # https://stackoverflow.com/a/28990982
            cfg = {s : dict(cfg.items(s))
                   for s in cfg.sections()}

            # Line breaks are interpreted as list separators
            for section in cfg.values():
                for key in section:
                    if '\n' in section[key]:
                        section[key] = [item for item in section[key].split('\n') if item]

            return cfg

    def __getitem__(self, key):
        if isinstance(key, str) and '.' in key:
            path = key.split('.') if isinstance(key, str) else list(key)
            value = self._cfg
            while path:
                value = value[path.pop(0)]
            return value
        else:
            return self._cfg[key]

    def __setitem__(self, key, value):
        if isinstance(key, str) and '.' in key:
            path = key.split('.') if isinstance(key, str) else list(key)
            target = self._cfg
            while len(path) > 1:
                key = path.pop(0)
                target = target[key]
            key = path.pop(0)
        else:
            target = self._cfg
        target[key] = value

    def __delitem__(self, key):
        self.reset(key)

    def __iter__(self):
        return iter(self._cfg)

    def __len__(self):
        return len(self._cfg)

    def __repr__(self):
        return repr(self._cfg)

    def copy(self):
        """Return deep copy as :class:`dict`"""
        return copy.deepcopy(self)

    def reset(self, path=()):
        """
        Set section, subsection or option to default value(s)

        :param path: Section, section and subsection or section, subsection and
            option as sequence or string with `"."` as delimiter
        """
        path = path.split('.') if isinstance(path, str) else list(path)
        while len(path) < 3:
            path.append('')
        self._reset(*path)

    def _reset(self, section=None, subsection=None, option=None):
        # Rename argument variables to untangle them from loop variables
        section_arg, subsection_arg, option_arg = section, subsection, option
        del section, subsection, option

        sections = (section_arg,) if section_arg else tuple(self._cfg)
        for section in sections:
            subsections = (subsection_arg,) if subsection_arg else tuple(self._cfg[section])
            for subsection in subsections:
                options = (option_arg,) if option_arg else tuple(self._cfg[section][subsection])
                for option in options:
                    self._cfg[section][subsection][option] = \
                        self._defaults[section][subsection][option]

    def write(self, *sections):
        """
        Save current configuration to file(s)

        :param sections: Paths to sections, subsections or options to save. Save
            all sections with no arguments.

        :raise ConfigError: if writing fails
        """
        if not sections:
            sections = tuple(self._files)
        else:
            sections = tuple(s.split('.')[0] for s in sections)

        for section in sections:
            parentdir = os.path.dirname(self._files[section])
            os.makedirs(parentdir, exist_ok=True)
            try:
                with open(self._files[section], 'w') as f:
                    f.write(self._as_ini(section))
            except OSError as e:
                raise errors.ConfigError(f'{self._files[section]}: {e.strerror or e}')

    def _as_ini(self, section):
        lines = []
        for subsection, options in self._cfg.get(section, {}).items():
            lines_subsection = []
            for option, value in options.items():
                if value == self._defaults[section][subsection][option]:
                    continue

                if utils.is_sequence(value):
                    if value:
                        values = '\n  '.join(str(v) for v in value)
                        lines_subsection.append(f'{option} =\n  {values}')
                    else:
                        lines_subsection.append(f'{option} =')
                else:
                    lines_subsection.append(f'{option} = {value}')

            if lines_subsection:
                lines.append(f'[{subsection}]')
                lines.extend(lines_subsection)

                # Empty line between subsections
                lines.append('')

        return '\n'.join(lines)


class _ConfigDict(collections.abc.MutableMapping):
    """
    Dictionary that only accepts certain keys and value types

    :param dict dct: Initial values
    :param dict keys: Allowed keys. Values are ignored. If omitted, keys from
        `dct` are used.
    :param dict types: Value converters, converters get a value and must return
        the value to store

    Getting or setting keys that are not in `keys` raises `KeyError`.

    Setting keys that are dictionaries to non-dictionaries raises `TypeError`.
    Setting keys that are non-dictionaries to dictionaries raises `TypeError`.

    Subdictionaries are always instances of this class with the appropriate
    `keys` and `types`.

    Setting an existing subdictionary to a dictionary copies values instead of
    replacing the subdictionary.
    """

    def __init__(self, dct, *, keys=None, types=None):
        assert isinstance(dct, collections.abc.Mapping)
        self._keys = self._build_keys(keys or dct)
        self._types = types or {}
        self._dct = {}
        for k, v in dct.items():
            self[k] = v

    def _build_keys(self, keys):
        built_keys = {}
        for k, v in keys.items():
            if isinstance(v, collections.abc.Mapping):
                built_keys[k] = self._build_keys(v)
            else:
                built_keys[k] = None
        return built_keys

    def __getitem__(self, key):
        return self._dct[key]

    def __delitem__(self, key):
        del self._dct[key]

    def __setitem__(self, key, value):
        self._dct[key] = self._convert(key, value)

    def _convert(self, key, value):
        if key not in self._keys:
            raise KeyError(key)

        if key in self._types:
            if not isinstance(self._types[key], collections.abc.Mapping):
                converter = self._types[key]
                try:
                    value = converter(value)
                except (ValueError, TypeError) as e:
                    raise errors.ConfigError(e)

        if isinstance(self._keys[key], collections.abc.Mapping):
            # Setting a subdictionary
            if not isinstance(value, collections.abc.Mapping):
                raise TypeError(
                    f'Expected dictionary for {key}, '
                    f'not {type(value).__name__}: {value!r}'
                )
            else:
                # Merge new dictionary into existing dictionary
                if key in self._dct:
                    value = utils.merge_dicts(self._dct[key], value)
                return _ConfigDict(
                    value,
                    keys=self._keys[key],
                    types=self._types.get(key, None),
                )
        elif isinstance(value, collections.abc.Mapping):
            # Key is not a dictionary, so value can't be one
            raise TypeError(f'{key} is not a dictionary: {value!r}')
        else:
            return value

    def __iter__(self):
        return iter(self._dct)

    def __len__(self):
        return len(self._dct)

    def __repr__(self):
        return repr(self._dct)

    def copy(self):
        """Return deep copy as :class:`dict`"""
        return copy.deepcopy(self)
