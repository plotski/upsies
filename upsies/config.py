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
    'trackers': {
        'nbl': _TrackerConfig(
            source='NBL',
        ),
        'bb': _TrackerConfig(
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
    },

    'clients': {
        'transmission': {
            'url': 'http://localhost:9091/transmission/rpc',
            'username': '',
            'password': '',
        },
    }
}


class Config:
    """
    Provide configuration file options

    :param str filepath: Path to configuration file

    :raises ConfigError: if reading or parsing `filepath` fails
    """
    def __init__(self, **files):
        self._files = files
        self._cfg = {}
        for section in self._files:
            self._cfg[section] = self._read(section)

    def defaults(self, section):
        return DEFAULTS[section]

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
