"""
Change or show configuration file options
"""

from .... import defaults, jobs, utils
from .base import CommandBase


def _make_pretty_option_list():
    lines = []
    for option in defaults.option_paths():
        option_type = defaults.option_type(option)
        if option_type is not str:
            lines.append(f'{option} ({option_type.__name__.lower()})')
        else:
            lines.append(option)
    return '\n  '.join(lines)


class set(CommandBase):
    """
    Change or show configuration file options

    Without any arguments, all options are listed with their current values.

    The first segment in OPTION is the file name without the extension. The
    second segment is the section name in that file. The third segment is the
    option name.

    List values are given as one argument per list item. If non-list values are
    given as multiple arguments, they are concatenated with single spaces. In
    the INI file, list items are delimited by one line break and one or more
    spaces (e.g. "\\n    ").

    Bytes values can handle units like "kB", "MB", "GiB", etc.
    """

    names = ('set',)

    description = 'options:\n  ' + _make_pretty_option_list()

    argument_definitions = {
        'OPTION': {
            'type': utils.argtypes.option,
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
