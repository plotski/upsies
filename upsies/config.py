import collections
import configparser
import copy
from os.path import exists as _path_exists

from . import errors

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Config:
    """
    Combine multiple INI-style configuration files into nested dictionaries

    Each top-level dictionary maps section names to sections (the configuration
    stored in one file). Each section maps section names from that file (which
    are subsections in this representation) to dictionaries that map option
    names to values.

    List values are stored with "\n" as a separator between list items.

    :param dict defaults: Nested directory structure as described above with
        default values
    :param str files: Map section names to file paths

    :raises ConfigError: if reading or parsing a file fails
    """
    def __init__(self, defaults, **files):
        self._defaults = copy.deepcopy(defaults)
        self._files = {}
        self._cfg = {}
        for section, subsection in self._defaults.items():
            self._cfg[section] = copy.deepcopy(subsection)
        for section, filepath in files.items():
            self.read(section, filepath)

    def read(self, section, filepath, ignore_missing=False):
        """
        Read `filepath` and make its contents available as `section`

        :raises ConfigError: if reading or parsing a file fails
        """
        if ignore_missing and not _path_exists(filepath):
            self._cfg[section] = {}
            self._files[section] = filepath
        else:
            try:
                with open(filepath, 'r') as f:
                    string = f.read()
            except OSError as e:
                raise errors.ConfigError(f'{filepath}: {e.strerror}')
            else:
                cfg = self._parse(section, string, filepath)
                cfg = self._validate_section(section, cfg, filepath)
                self._cfg[section] = self._apply_defaults(section, cfg)
                self._files[section] = filepath

    def defaults(self, section):
        """
        Return the defaults for `section`

        :raises ValueError: if `section` does not exist
        """
        try:
            return self._defaults[section]
        except KeyError:
            raise ValueError(f'No such section: {section}')

    def _parse(self, section, string, filepath):
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

    def _validate_section(self, section, cfg, filepath):
        if section not in self._defaults:
            raise errors.ConfigError(f'{section}: Unknown section')

        defaults = self.defaults(section)
        for subsect in cfg:
            if subsect not in defaults:
                raise errors.ConfigError(f'{filepath}: {subsect}: Unknown section')
            for option in cfg[subsect]:
                if option not in defaults[subsect]:
                    raise errors.ConfigError(
                        f'{filepath}: {subsect}: {option}: Unknown option')

        return cfg

    def _apply_defaults(self, section, cfg):
        defaults = self.defaults(section)
        for subsect in defaults:
            if subsect not in cfg:
                cfg[subsect] = defaults[subsect]
            else:
                for option in defaults[subsect]:
                    if option not in cfg[subsect]:
                        cfg[subsect][option] = defaults[subsect][option]
        return cfg

    def __getitem__(self, key):
        return ImmutableDict(**self._cfg[key])


class ImmutableDict(collections.abc.Mapping):
    def __init__(self, *args, **kwargs):
        self._dict = dict(*args, **kwargs)
        print('id: %r', repr(self._dict))

    def __getitem__(self, key):
        print('getting key:', key)
        return self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __repr__(self):
        return repr(self._dict)
