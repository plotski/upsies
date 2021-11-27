"""
Change or show configuration file options
"""

import textwrap

from .... import constants, defaults, errors, jobs, utils
from .base import CommandBase


def _make_pretty_option_list():
    lines = []
    for option in defaults.option_paths():
        option_type = defaults.option_type(option)
        option_type_name = option_type.__name__.lower()
        file, section, name = option.split('.', maxsplit=2)
        default_value = defaults.defaults[file][section][name]
        text = [f'{option} ({option_type_name})']

        if option_type_name == 'list':
            if default_value:
                text.append(f'  Default: {default_value[0]}')
                for item in default_value[1:]:
                    text.append(f'           {item}')
            else:
                text.append('  Default: <empty>')
        else:
            text.append(f'  Default: {default_value}')

        if option_type_name == 'int':
            option_type_name = 'integer'
        elif option_type_name == 'str':
            option_type_name = 'string'
        elif option_type_name == 'choice':
            text.append(f'  Choices: {", ".join(default_value.options)}')

        # Add description indented
        description = getattr(option_type, 'description', '')
        if description:
            description_lines = []
            for paragraph in description.strip().split('\n'):
                description_lines.extend(
                    textwrap.wrap(
                        text=paragraph,
                        width=72,
                    )
                )
            text.extend('  ' + line for line in description_lines)
        lines.append('\n  '.join(text))

    return '\n\n  '.join(lines)


class set(CommandBase):
    """
    Change or show configuration file options

    Without any arguments, all options are listed with their current values.

    OPTION consists of three segments which are delimited with a period (".").
    The first segment in OPTION is the file name without the extension. The
    second segment is the section name in that file. The third segment is the
    option name.

    List values are given as one argument per list item. If non-list values are
    given as multiple arguments, they are concatenated with single spaces. In
    the INI file, list items are delimited by one line break and one or more
    spaces (e.g. "\\n    ").
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
        ('--fetch-ptpimg-apikey',): {
            'nargs': 2,
            'metavar': ('EMAIL', 'PASSWORD'),
            'help': ('Fetch ptpimg API key and save it in '
                     f'{utils.fs.tildify_path(constants.IMGHOSTS_FILEPATH)}\n'
                     '(EMAIL and PASSWORD are not saved)'),
        },
    }

    @utils.cached_property
    def jobs(self):
        if self.args.fetch_ptpimg_apikey is not None:
            return (self.fetch_ptpimg_apikey_job,)
        else:
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

    @utils.cached_property
    def fetch_ptpimg_apikey_job(self):
        return jobs.custom.CustomJob(
            name='fetch-ptpimg-apikey',
            label='API key',
            worker=self.fetch_ptpimg_apikey,
            catch=(errors.RequestError, errors.ConfigError),
            ignore_cache=self.args.ignore_cache,
        )

    async def fetch_ptpimg_apikey(self, job):
        if len(self.args.fetch_ptpimg_apikey) <= 0:
            job.error('Missing EMAIL and PASSWORD')
        elif len(self.args.fetch_ptpimg_apikey) <= 1:
            job.error('Missing PASSWORD')
        elif len(self.args.fetch_ptpimg_apikey) > 2:
            unknown_args = ' '.join(self.args.fetch_ptpimg_apikey[2:])
            job.error(f'Unrecognized arguments: {unknown_args}')
        else:
            email = self.args.fetch_ptpimg_apikey[0]
            password = self.args.fetch_ptpimg_apikey[1]
            ptpimg = utils.imghosts.imghost('ptpimg')
            apikey = await ptpimg.get_apikey(email, password)
            job.send(apikey)
            self.config['imghosts']['ptpimg']['apikey'] = apikey
            self.config.write('imghosts.ptpimg.apikey')
            job.finish()
