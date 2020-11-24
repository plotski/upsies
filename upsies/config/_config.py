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
                raise errors.ConfigError(f'{filepath}: {subsect}: Unknown subsection')
            for option in cfg[subsect]:
                if option not in defaults[subsect]:
                    raise errors.ConfigError(
                        f'{filepath}: {subsect}: {option}: Unknown option')
                else:
                    self._validate_value(section, subsect, option, cfg[subsect][option])
        return cfg

    def _validate_value(self, section, subsection, option, value):
        default = self._defaults[section][subsection][option]
        if utils.is_sequence(default) and not utils.is_sequence(value):
            return value.split()
        elif not utils.is_sequence(default) and utils.is_sequence(value):
            return ' '.join(str(v) for v in value)
        else:
            return str(value)

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

    def _validate_path(self, path):
        segments = path.split('.', maxsplit=3)
        if len(segments) == 1:
            raise errors.ConfigError(f'{path}: Missing subsection and option')
        elif len(segments) == 2:
            raise errors.ConfigError(f'{path}: Missing option')
        else:
            section_name, subsection_name, option_name = segments

        try:
            section = self[section_name]
        except KeyError:
            raise errors.ConfigError(f'{section_name}: Unknown section')
        try:
            subsection = section[subsection_name]
        except KeyError:
            raise errors.ConfigError(f'{subsection_name}: Unknown subsection in section {section_name}')
        try:
            subsection[option_name]
        except KeyError:
            raise errors.ConfigError(f'{option_name}: Unknown option in subsection {section_name}.{subsection_name}')

        return section_name, subsection_name, option_name

    def __getitem__(self, key):
        if '.' in key:
            section, subsection, option = self._validate_path(key)
            return self._cfg[section][subsection][option]
        else:
            return _ImmutableDict(self._cfg[key])

    def set(self, path, value):
        """
        Change option value

        :param str path: Path to option in the format
            "<section>.<subsection>.<option>"
        :param value: New value for option specified by `path`

        :raise ConfigError: if the operation fails
        """
        section, subsection, option = self._validate_path(path)
        value = self._validate_value(section, subsection, option, value)
        self._cfg[section][subsection][option] = value

    def reset(self, path):
        """
        Reset option value to default

        :param str path: Path to option in the format
            "<section>.<subsection>.<option>"

        :raise ConfigError: if `path` is not a valid option
        """
        section, subsection, option = self._validate_path(path)
        self._cfg[section][subsection][option] = self._defaults[section][subsection][option]

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
        for subsection, options in self[section].items():
            lines.append(f'[{subsection}]')
            for option, value in options.items():
                if utils.is_sequence(value):
                    if value:
                        lines.append(f'{option} =\n  ' + '\n  '.join(value))
                    else:
                        lines.append(f'{option} =')
                else:
                    lines.append(f'{option} = {value}')
            # Empty line between subsections
            lines.append('')
        return '\n'.join(lines)


class _ImmutableDict(collections.abc.Mapping):
    def __init__(self, dct):
        self._dict = {}
        for k, v in dct.items():
            if isinstance(v, dict):
                self._dict[k] = _ImmutableDict(v)
            else:
                self._dict[k] = v

    def __getitem__(self, key):
        return self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __repr__(self):
        return repr(self._dict)
