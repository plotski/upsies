from .. import errors, utils
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SetJob(JobBase):
    """
    Change or show option in configuration file

    :param config: :class:`config.Config` instance
    :param str option: "."-delimited path to option or None to display all options
    :param value: New value for `option` or `None` to display the current value
    :param bool reset: Whether to reset `option` to default value
    """

    name = 'set'
    label = 'Set'
    hidden = True
    cache_file = None

    def initialize(self, *, config, option=None, value=None, reset=None):
        try:
            if not option:
                if value:
                    raise RuntimeError('Argument "value" cannot be given if "option" is not given.')
                else:
                    for o in config.paths:
                        self.display_option(config, o)
            elif value and reset:
                raise RuntimeError('Arguments "value" and "reset" cannot both be given.')
            else:
                if reset:
                    config.reset(option)
                    config.write(option)
                elif value:
                    config[option] = value
                    config.write(option)
                self.display_option(config, option)
        except errors.ConfigError as e:
            self.error(e)
        finally:
            self.finish()

    def display_option(self, config, option):
        if utils.is_sequence(config[option]):
            self.send(f'{option} = {" ".join(config[option])}')
        else:
            self.send(f'{option} = {config[option]}')

    def execute(self):
        pass
