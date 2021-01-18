"""
Change or show configuration file options
"""

from .... import constants, jobs, utils
from .base import CommandBase


class set(CommandBase):
    """
    Change or show configuration file options

    Without any arguments, all options are listed with their current values.

    The first segment in the option name is the file name without the
    extension. The second segment is the section name in that file. The third
    segment is the option name.

    List values must be given as separate arguments. If non-list values are
    given as multiple arguments, they are concatenated with single spaces.
    """

    names = ('set',)

    description = ('options:\n  ' + '\n  '.join(o for o in constants.OPTION_PATHS))

    argument_definitions = {
        'OPTION': {
            'type': utils.types.OPTION,
            'nargs': '?',
            'help': 'Option to change or show',
        },
        'VALUE': {
            'nargs': '*',
            'default': '',  # FIXME: https://bugs.python.org/issue41854
            'help': 'New value for OPTION',
            'group': 'value',
        },
        ('--reset', '-r'): {
            'action': 'store_true',
            'help': 'Reset OPTION to default value',
            'group': 'value',
        },
    }

    @utils.cached_property
    def jobs(self):
        return (
            jobs.config.SetJob(
                config=self.config,
                option=self.args.OPTION,
                # VALUE is a list. The Config class should convert lists to
                # strings (and vice versa) depending on the default type.
                value=self.args.VALUE,
                reset=self.args.reset,
            ),
        )
