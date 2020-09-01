import configparser
import os

from . import errors

import logging  # isort:skip
_log = logging.getLogger(__name__)


class _TrackerConfig(dict):
    _defaults = {
        'username' : '',
        'password' : '',
        'announce' : '',
        'source'   : '',
        'exclude'  : [],
    }

    def __new__(cls, **kwargs):
        return {**cls._defaults, **kwargs}


DEFAULTS = {
    'nbl': _TrackerConfig(
        source='NBL',
    ),
    'bb': _TrackerConfig(
        source='bB',
        exclude=[
            r'\.(?i:nfo)$',
            r'\.(?i:jpg)$',
            r'\.(?i:png)$',
            rf'(?:{os.path.sep}|^)(?i:sample)(?:{os.path.sep}|\.[a-zA-Z0-9]+$)',
            rf'(?:{os.path.sep}|^)(?i:proof)(?:{os.path.sep}|\.[a-zA-Z0-9]+$)',
        ],
    ),
}


class Config:
    """
    Provide configuration file options

    :param str filepath: Path to configuration file

    :raises ConfigError: if reading or parsing `filepath` fails
    """
    def __init__(self, filepath):
        self._filepath = str(filepath)

        try:
            with open(filepath, 'r') as f:
                string = f.read()
        except OSError as e:
            raise errors.ConfigError(f'{filepath}: {e.strerror}')

        cfg = self._parse(string)
        cfg = self._validate(cfg, DEFAULTS)
        self._cfg = self._apply_defaults(cfg, DEFAULTS)

    def _parse(self, string):
        cfg = configparser.ConfigParser(
            default_section=None,
        )
        try:
            cfg.read_string(string, source=self._filepath)
        except configparser.Error as e:
            raise errors.ConfigError(f'{self._filepath}: {e}')
        else:
            # Make normal dictionary from ConfigParser instance
            # https://stackoverflow.com/a/28990982
            return {s : dict(cfg.items(s))
                    for s in cfg.sections()}

    def _validate(self, cfg, defaults):
        for section in cfg:
            if section not in defaults:
                raise errors.ConfigError(f'{self._filepath}: Unknown section: {section}')
            for option in cfg[section]:
                if option not in defaults[section]:
                    raise errors.ConfigError(
                        f'{self._filepath}: Unknown option in section {section}: {option}')
        return cfg

    def _apply_defaults(self, cfg, defaults):
        for section in defaults:
            if section not in cfg:
                cfg[section] = defaults[section]
            else:
                for option in defaults[section]:
                    if option not in cfg[section]:
                        cfg[section][option] = defaults[section][option]
        return cfg

    def option(self, section, option):
        try:
            section_dct = self._cfg[section]
        except KeyError:
            raise errors.ConfigError(f'{self._filepath}: No such section: {section}')
        else:
            try:
                value = section_dct[option]
            except KeyError:
                raise errors.ConfigError(
                    f'{self._filepath}: No such option for section {section}: {option}')
            else:
                return value
