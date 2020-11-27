import collections
import configparser
import copy
from os.path import exists as _path_exists

from .. import errors, utils

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Config:
    """
    Combine multiple INI-style configuration files into nested dictionaries

    Each top-level dictionary maps section names to subsections. A section name
    is associated with an INI file. Subsections are sections in an INI
    file. Subsections contain pairs of options and values.

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

    List values are stored with "\n" as a separator between list items.

    :param defaults: Nested directory structure as described above with
        default values
    :param files: Map section names to file paths that are :meth:`read`
        immediately

    :raises ConfigError: if :meth:`read`ing fails
    """

    _converters = {
        str: lambda value: value.split(),
        collections.abc.Sequence: lambda value: ' '.join(value),
        None: str,
    }

    def __init__(self, defaults, **files):
        self._defaults = copy.deepcopy(defaults)
        self._cfg = _SpecDict(
            spec=defaults,
            dct=defaults,
            converters=self._converters,
        )
        # _files maps section names to file paths.
        self._files = {}
        for section, filepath in files.items():
            self.read(section, filepath)

    def __repr__(self):
        return repr(self._cfg)

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
            except TypeError as e:
                raise errors.ConfigError(f'{section}.{subsection}.{option}: {e}')

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
                _log.debug('Config after reading %r: %r', filepath, self._cfg)

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
        if '.' in key:
            path = key.split('.') if isinstance(key, str) else list(key)
            value = self._cfg
            while path:
                value = value[path.pop(0)]
            return value
        else:
            return self._cfg[key]

    def __setitem__(self, key, value):
        if '.' in key:
            path = key.split('.') if isinstance(key, str) else list(key)
            target = self._cfg
            while len(path) > 1:
                key = path.pop(0)
                target = target[key]
            key = path.pop(0)
        else:
            target = self._cfg
        target[key] = value

    def reset(self, path=()):
        """
        Set `path` to default value

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
            try:
                with open(self._files[section], 'w') as f:
                    f.write(self._as_ini(section))
            except OSError as e:
                raise errors.ConfigError(f'{self._files[section]}: {e.strerror or e}')

    def _as_ini(self, section):
        lines = []
        for subsection, options in self._cfg.get(section, {}).items():
            lines.append(f'[{subsection}]')
            for option, value in options.items():
                if utils.is_sequence(value):
                    if value:
                        lines.append(f'{option} =\n  ' + '\n  '.join(str(v) for v in value))
                    else:
                        lines.append(f'{option} =')
                else:
                    lines.append(f'{option} = {value}')
            # Empty line between subsections
            lines.append('')
        return '\n'.join(lines)


# Inherit from MutableMapping to get the ABC benefits.
# Inherit from dict so that `isinstance(spec_dict_instance, dict)` returns True.
class _SpecDict(collections.abc.MutableMapping, dict):
    """
    Dictionary that only accepts certain keys and value types

    :param dict spec: Map allowed keys to value types. Values can be classes or
        instances. Only the class of instances is stored.
    :param dict dct: Initial values
    :param dict converters: Dictionary of classes to callables that take a value of
        one type and return a value of a different type, e.g. to convert strings
        to lists.

        Keys are classes or tuples of classes. Any value that is a subclass of
        the key passed to the associated converter function and the return value
        is used as the value.

        The converter with the key `None` is used as a default instead of
        raising `TypeError`.

        Exceptions from converter functions are unhandled.

    Getting or setting keys that are not in `spec` raises `KeyError`.

    Setting keys to values that are not subclasses of what is specified in
    `spec` raises `TypeError` if there is no converter available for their
    class.

    Nested dictionaries are recursively converted to `_SpecDict` instances.

    Setting subdictionaries updates the existing values instead of replacing
    them.
    """

    def __init__(self, spec, dct, converters=None):
        self._spec = self._build_spec(spec)
        self._dct = {}
        self._converters = converters or {}
        for k, v in dct.items():
            self[k] = v

    def _build_spec(self, spec):
        built_spec = {}
        for k, v in spec.items():
            if isinstance(v, dict):
                built_spec[k] = self._build_spec(v)
            elif isinstance(v, type):
                built_spec[k] = v
            else:
                built_spec[k] = type(v)
        return built_spec

    def __getitem__(self, key):
        return self._dct[key]

    def __delitem__(self, key):
        del self._dct[key]

    def __setitem__(self, key, value):
        if key not in self._spec:
            raise KeyError(key)
        elif isinstance(self._spec[key], dict):
            if not isinstance(value, dict):
                raise TypeError(
                    f'Expected {dict.__name__} for {key}, '
                    f'not {type(value).__name__}: {value!r}'
                )
            if key in self._dct:
                value = utils.merge_dicts(self._dct[key], value)
            self._dct[key] = _SpecDict(spec=self._spec[key], dct=value, converters=self._converters)
        else:
            self._dct[key] = self._convert(key, value)

    def _convert(self, key, value):
        if isinstance(value, self._spec[key]):
            return value

        for typ, converter in self._converters.items():
            # `typ` may be single type or tuple of types
            if typ is not None and  isinstance(value, typ):
                return converter(value)

        # Use default converter or raise TypeError
        if None in self._converters:
            return self._converters[None](value)
        else:
            raise TypeError(
                f'Expected {self._spec[key].__name__} for {key}, '
                f'not {type(value).__name__}: {value!r}'
            )

    def __iter__(self):
        return iter(self._dct)

    def __len__(self):
        return len(self._dct)

    def __repr__(self):
        return repr(self._dct)
