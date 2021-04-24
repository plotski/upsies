"""
Manage configuration files
"""

from .. import errors, utils
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SetJob(JobBase):
    """Change or show option in configuration file"""

    name = 'set'
    label = 'Set'
    hidden = True
    cache_id = None  # Don't cache output

    def initialize(self, *, config, option=None, value='', reset=None):
        """
        Set and display option(s)

        :param config: :class:`~.configfiles.ConfigFiles` instance
        :param str option: "."-delimited path to option in `config` or `None`
        :param value: New value for `option` or any falsy value to display the
            current value
        :param bool reset: Whether to reset `option` to default value and ignore
            `value`

        If only `config` is given, display all options and values.

        If `option` is given, display only its value.

        If `option` and `value` is given, set `option` to `value` display the
        result.
        """
        if value and reset:
            raise RuntimeError('Arguments "value" and "reset" are mutually exclusive.')
        elif value and not option:
            raise RuntimeError('Argument "value" needs argument "option".')
        else:
            self._config = config
            self._option = option
            self._value = value
            self._reset = reset

    def execute(self):
        try:
            if self._reset:
                self._reset_mode()
            elif self._value:
                self._set_mode()
            else:
                self._display_mode()
        except errors.ConfigError as e:
            self.error(e)
        finally:
            self.finish()

    def _reset_mode(self):
        if self._option:
            self._config.reset(self._option)
            self._write(self._option)
        else:
            for o in self._config.paths:
                self._config.reset(o)
                self._write(o)

    def _set_mode(self):
        self._config[self._option] = self._value
        self._write(self._option)

    def _display_mode(self):
        if self._option:
            self._display_option(self._option)
        else:
            for o in self._config.paths:
                self._display_option(o)

    def _write(self, option):
        self._config.write(option)
        self._display_option(option)

    def _display_option(self, option):
        if utils.is_sequence(self._config[option]):
            values = '\n  '.join(str(v) for v in self._config[option])
            if values:
                self.send(f'{option} =\n  ' + values)
            else:
                self.send(f'{option} =')
        else:
            self.send(f'{option} = {self._config[option]}')
