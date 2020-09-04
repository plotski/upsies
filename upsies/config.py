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
    'tracker:nbl': _TrackerConfig(
        source='NBL',
    ),
    'tracker:bb': _TrackerConfig(
        source='bB',
        exclude=[
            r'\.(?i:jpg)$',
            r'\.(?i:png)$',
            r'\.(?i:nfo)$',
            r'\.(?i:txt)$',
            rf'(?:{os.path.sep}|^)(?i:sample)(?:{os.path.sep}|\.[a-zA-Z0-9]+$)',
            rf'(?:{os.path.sep}|^)(?i:proof)(?:{os.path.sep}|\.[a-zA-Z0-9]+$)',
        ],
    ),
    'client:transmission': {
        'username': '',
        'password': '',
        'url': '',
    },
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
            cfg = {s : dict(cfg.items(s))
                   for s in cfg.sections()}
            # Line breaks are interpreted as list separators
            for section in cfg.values():
                for key in section:
                    if '\n' in section[key]:
                        section[key] = [item for item in section[key].split('\n') if item]
            return cfg

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

    def section(self, section):
        try:
            return self._cfg[section]
        except KeyError:
            raise errors.ConfigError(f'{self._filepath}: No such section: {section}')
