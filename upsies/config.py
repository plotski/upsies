import configparser
import os

from . import errors

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Config:
    """
    Provide configuration file options

    :param str filepath: Path to configuration file

    :raises ConfigError: if reading or parsing `filepath` fails
    """
    def __init__(self, defaults, **files):
        self._defaults = defaults
        self._files = files
        self._cfg = {}
        for section in self._files:
            self._cfg[section] = self._read(section)

    def defaults(self, section):
        return self._defaults[section]

    def _read(self, section):
        if os.path.exists(self._files[section]):
            try:
                with open(self._files[section], 'r') as f:
                    string = f.read()
            except OSError as e:
                raise errors.ConfigError(f'{self._files[section]}: {e.strerror}')
            else:
                cfg = self._parse(section, string)
        else:
            cfg = {}
        cfg = self._validate(section, cfg)
        return self._apply_defaults(section, cfg)

    def _parse(self, section, string):
        cfg = configparser.ConfigParser(
            default_section=None,
        )
        try:
            cfg.read_string(string, source=self._files[section])
        except configparser.Error as e:
            raise errors.ConfigError(f'{self._files[section]}: {e}')
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

    def _validate(self, section, cfg):
        defaults = self.defaults(section)
        for section in cfg:
            if section not in defaults:
                raise errors.ConfigError(f'{self._files[section]}: Unknown section: {section}')
            for option in cfg[section]:
                if option not in defaults[section]:
                    raise errors.ConfigError(
                        f'{self._files[section]}: Unknown option in section {section}: {option}')
        return cfg

    def _apply_defaults(self, section, cfg):
        defaults = self.defaults(section)
        for sect in defaults:
            if sect not in cfg:
                cfg[sect] = defaults[sect]
            else:
                for option in defaults[sect]:
                    if option not in cfg[sect]:
                        cfg[sect][option] = defaults[sect][option]
        return cfg

    def __getitem__(self, key):
        return self._cfg[key]
