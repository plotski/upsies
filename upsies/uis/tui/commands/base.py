"""
Abstract base class for commands
"""

import abc
import argparse
import collections
import os
import re
import sys
import textwrap

from .... import (__description__, __project_name__, __version__, constants,
                  defaults, errors, utils)
from ....utils import configfiles

import logging  # isort:skip
_log = logging.getLogger(__name__)


class _MyHelpFormatter(argparse.HelpFormatter):
    """Use "\n" to separate and preserve paragraphs and limit line width"""

    MAX_WIDTH = 90

    def __init__(self, *args, **kwargs):
        import shutil
        width_available = shutil.get_terminal_size().columns
        super().__init__(*args,
                         width=min(width_available, self.MAX_WIDTH),
                         **kwargs)

    def _fill_text(self, text, width, indent):
        return '\n'.join(self.__wrap_paragraphs(text, width))

    def _split_lines(self, text, width):
        return self.__wrap_paragraphs(text, width)

    def __wrap_paragraphs(self, text, width, indent=''):
        def wrap(text):
            if not text:
                return ['']
            else:
                return textwrap.wrap(
                    text=text,
                    width=min(width, self.MAX_WIDTH),
                    replace_whitespace=False,
                    initial_indent=indent,
                    subsequent_indent=indent,
                )

        width = min(width, self.MAX_WIDTH) - len(indent)
        text = re.sub(r'``(.*?)``', '\x1b[3m\\1\x1b[23m', text)
        return [line
                for paragraph in text.split('\n')
                for line in wrap(paragraph)]


class CommandBase(abc.ABC):
    """
    Base class for all commands

    :meth:`register` must be called on all subclasses.

    Instead of instantiating subclasses normally, the class method :meth:`run`
    should be used to get instances.

    :param args: Command line arguments
    :param config: :class:`~.configfiles.ConfigFiles` object
    """

    _argparser = argparse.ArgumentParser(
        description=__description__,
        formatter_class=_MyHelpFormatter,
    )
    _argparser.add_argument('--version',
                            action='version',
                            version=f'{__project_name__} {__version__}')
    _argparser.add_argument('--debug', '-d',
                            metavar='FILE',
                            help='Write debugging messages to FILE')
    _argparser.add_argument('--config-file', '-f',
                            help='General configuration file path',
                            default=constants.CONFIG_FILEPATH)
    _argparser.add_argument('--trackers-file', '-t',
                            help='Trackers configuration file path',
                            default=constants.TRACKERS_FILEPATH)
    _argparser.add_argument('--imghosts-file', '-i',
                            help='Image hosting services configuration file path',
                            default=constants.IMGHOSTS_FILEPATH)
    _argparser.add_argument('--clients-file', '-c',
                            help='BitTorrent clients configuration file path',
                            default=constants.CLIENTS_FILEPATH)
    _argparser.add_argument('--ignore-cache', '-C',
                            help='Ignore results from previous calls',
                            action='store_true')

    # Commands
    _subparsers = _argparser.add_subparsers(title='commands')

    # Mutually exclusive arguments
    _mutex_groups = collections.defaultdict(lambda: {})

    names = NotImplemented
    """
    Sequence of command names

    The first name is the full name and the rest are short aliases.
    """

    argument_definitions = NotImplemented
    """
    CLI argument definitions for this command

    This is a :class:`dict` in which keys are option names or flags
    (e.g. ``"PATH"`` or ``("--path", "-p")`` and each value is a :class:`dict`
    with keyword arguments for :meth:`argparse.ArgumentParser.add_argument`.

    Additionally, you may specify a ``group`` in each keyword argument
    dictionary. Arguments with the same ``group`` value are mutually exclusive,
    meaning the user can only specify one of them.
    """

    subcommands = {}
    """
    Subcommands of commands (or subsubcommands from a CLI point of view)

    This is a :class:`dict` where keys are subcommand names and values are
    :attr:`argument_definitions`.
    """

    description = ''
    """
    Extended description

    The class docstring is the main description. Use this attribute to generate
    text programmatically.
    """

    @classmethod
    def register(cls):
        """
        Add the command and its arguments to the internal
        :class:`argparse.ArgumentParser` instance

        This classmethod must be called on every subclass.
        """
        if cls.description:
            description = textwrap.dedent(cls.__doc__.strip('\n')) + '\n\n' + cls.description
        else:
            description = textwrap.dedent(cls.__doc__.strip('\n'))

        help = description.split('\n', 1)[0]
        parser = cls._subparsers.add_parser(
            cls.names[0],
            aliases=cls.names[1:],
            help=help,
            description=description,
            formatter_class=_MyHelpFormatter,
        )
        parser.set_defaults(command=cls)

        # Add options and flags for this command
        cls._add_args(parser, cls.argument_definitions, cls._mutex_groups[None])

        # Add subcommands
        if cls.subcommands:
            subparsers = parser.add_subparsers()
            for subcmd, args in cls.subcommands.items():
                subparser = subparsers.add_parser(subcmd, formatter_class=_MyHelpFormatter)
                subparser.set_defaults(subcommand=subcmd)
                cls._add_args(subparser, args, cls._mutex_groups[subcmd])

    @staticmethod
    def _add_args(parser, argument_definitions, mutex_groups):
        for argname, argopts in argument_definitions.items():
            names = (argname,) if isinstance(argname, str) else argname
            group_name = argopts.pop('group', None)
            if group_name:
                # Put arguments with the same argopts["group"] in a mutually
                # exclusive group.
                # FIXME: https://bugs.python.org/issue41854
                if not names[0].startswith('-') and argopts.get('default') is None:
                    raise RuntimeError('Default values of mutually exclusive positional arguments '
                                       'must not be None. See: https://bugs.python.org/issue41854')
                if group_name not in mutex_groups:
                    mutex_groups[group_name] = parser.add_mutually_exclusive_group()
                mutex_groups[group_name].add_argument(*names, **argopts)

            else:
                # Allow using REMAINDER flag without importing argparse
                # everywhere. This also introduces an abstraction layer in case
                # we ever use something else than argparse.
                if argopts.get('nargs') == 'REMAINDER':
                    argopts['nargs'] = argparse.REMAINDER

                parser.add_argument(*names, **argopts)

    @classmethod
    def run(cls, args):
        """
        Execute command

        :param args: Sequence of CLI arguments or `None` to use `sys.argv`
        """
        try:
            if args is None:
                main_args, remaining_args = cls._argparser.parse_known_args()
            else:
                main_args, remaining_args = cls._argparser.parse_known_args(args)
        except SystemExit as e:
            # argparse has sys.exit(2) hardcoded for CLI errors.
            raise SystemExit(e.code if e.code in (0, 1) else 1)

        # Show help if no command given
        if not hasattr(main_args, 'command'):
            cls._argparser.print_help()
            raise SystemExit(0)

        # Debugging
        if main_args.debug:
            logging.basicConfig(
                format='%(asctime)s: %(name)s: %(message)s',
                filename=main_args.debug,
            )
            logging.getLogger(__project_name__).setLevel(level=logging.DEBUG)

        # Read config files
        try:
            config = configfiles.ConfigFiles(defaults=defaults.defaults)
            config.read('config', filepath=main_args.config_file, ignore_missing=True)
            config.read('trackers', filepath=main_args.trackers_file, ignore_missing=True)
            config.read('imghosts', filepath=main_args.imghosts_file, ignore_missing=True)
            config.read('clients', filepath=main_args.clients_file, ignore_missing=True)
        except errors.ConfigError as e:
            print(e, file=sys.stderr)
            raise SystemExit(1)

        return main_args.command(args=args, config=config)

    def __init__(self, args, config):
        self._args = self._argparser.parse_args(args)
        self._config = config

    @property
    @abc.abstractmethod
    def jobs(self):
        """
        Sequence of :class:`~.jobs.base.JobBase` objects

        For convenience, the sequence may also contain `None` instead.
        """

    @property
    def jobs_active(self):
        """Same as :attr:`jobs` but without `None` values"""
        return [j for j in self.jobs if j is not None]

    @property
    def args(self):
        """Parsed CLI arguments as :class:`argparse.Namespace` object"""
        return self._args

    @property
    def config(self):
        """Config file options as :class:`~.configfiles.ConfigFiles` object"""
        return self._config

    @property
    def home_directory(self):
        """
        Passed as `home_directory` argument to :class:`.jobs.base.JobBase` instances
        that are instantiated by this class

        The default implementation passes the ``CONTENT`` or ``RELEASE``
        argument and ``config.main.cache_directory`` to :func:`.fs.projectdir`.

        If no ``CONTENT`` or ``RELEASE`` argument exists, return
        ``config.main.cache_directory`` directly.
        """
        if hasattr(self.args, 'CONTENT'):
            content_path = self.args.CONTENT
        elif hasattr(self.args, 'RELEASE'):
            content_path = self.args.RELEASE
        else:
            return self.config['config']['main']['cache_directory']

        return utils.fs.projectdir(
            content_path=content_path,
            base=self.config['config']['main']['cache_directory'],
        )

    @property
    def cache_directory(self):
        """
        Passed as `cache_directory` argument to :class:`.jobs.base.JobBase`
        instances that are instantiated by this class

        The default implementation appends ``.cache`` to :attr:`home_directory`
        if the ``CONTENT`` or ``RELEASE`` argument exists and returns
        ``config.main.cache_directory`` otherwise.
        """
        if hasattr(self.args, 'CONTENT') or hasattr(self.args, 'RELEASE'):
            return os.path.join(self.home_directory, '.cache')
        else:
            return self.config['config']['main']['cache_directory']
