from .. import errors
from . import JobBase


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

    def initialize(self, *, config, option, value=None):
        try:
            if value is not None:
                config.set(option, value)
                config.write(option)
        except errors.ConfigError as e:
            self.error(e)
        else:
            self.send(f'{option} = {config[option]}')
        finally:
            self.finish()

    def execute(self):
        pass
