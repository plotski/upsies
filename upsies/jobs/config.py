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
        try:
            if reset:
                self._reset_mode(config, option, value, reset)
            elif value:
                self._set_mode(config, option, value, reset)
            else:
                self._display_mode(config, option, value, reset)
        except errors.ConfigError as e:
            self.error(e)
        finally:
            self.finish()

    def _reset_mode(self, config, option, value, reset):
        if value:
            raise RuntimeError('Arguments "value" and "reset" are mutually exclusive.')
        if option:
            config.reset(option)
            self._write(config, option)
        else:
            for o in config.paths:
                config.reset(o)
                self._write(config, o)

    def _set_mode(self, config, option, value, reset):
        if reset:
            raise RuntimeError('Arguments "value" and "reset" are mutually exclusive.')
        elif not option:
            raise RuntimeError('Argument "value" needs argument "option".')
        else:
            config[option] = value
            self._write(config, option)

    def _display_mode(self, config, option, value, reset):
        if option:
            self._display_option(config, option)
        else:
            for o in config.paths:
                self._display_option(config, o)

    def _write(self, config, option):
        config.write(option)
        self._display_option(config, option)

    def _display_option(self, config, option):
        if utils.is_sequence(config[option]):
            self.send(f'{option} = {" ".join(str(v) for v in config[option])}')
        else:
            self.send(f'{option} = {config[option]}')
