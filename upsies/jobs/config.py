from .. import errors, utils
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SetJob(JobBase):
    """
    Change or show option in configuration file

    :param config: :class:`config.Config` instance
    :param str option: "."-delimited path to option
    :param value: New value for `option` or `None` to display the current value
    """

    name = 'set'
    label = 'Set'
    hidden = True
    cache_file = None

    def initialize(self, *, config, option, value=None, reset=False):
        if value and reset:
            raise RuntimeError('Arguments "value" and "reset" cannot both be given.')
        try:
            if reset:
                config.reset(option)
                config.write(option)
            elif value:
                config[option] = value
                config.write(option)
        except errors.ConfigError as e:
            self.error(e)
        else:
            if utils.is_sequence(config[option]):
                self.send(f'{option} = {" ".join(config[option])}')
            else:
                self.send(f'{option} = {config[option]}')
        finally:
            self.finish()

    def execute(self):
        pass
