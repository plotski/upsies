import argparse
import functools
import sys
import textwrap

from ... import __project_name__, __version__, constants, trackers, utils
from ...tools import btclient as btclients
from ...tools import imghost as imghosts
from ...tools import webdbs
from . import commands

import logging  # isort:skip
_log = logging.getLogger(__name__)


@functools.lru_cache(maxsize=None)
def _get_names(package, clsname, name_attribute):
    """
    Get user-facing names from modules or classes in a package

    :param package package: Package from where to collect names
    :param str clsname: Common class name of every module in `package`; if this is
        falsy, get `name_attribute` from the modules directly
    :param str name_attribute: Name of the attribute that stores the name we
        want
    """
    import inspect
    modules = (module for name, module in inspect.getmembers(package, inspect.ismodule)
               if not name.startswith('_'))
    if clsname:
        # Get name from a common class name
        clsses = [getattr(module, clsname) for module in modules]
        return [utils.CaseInsensitiveString(getattr(cls, name_attribute))
                for cls in clsses]
    else:
        # Get name from each module
        return [utils.CaseInsensitiveString(getattr(mod, name_attribute))
                for mod in modules]

DB_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in webdbs.webdbs()]
TRACKER_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in trackers.trackers()]
IMGHOST_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in imghosts.imghosts()]
BTCLIENT_NAMES = [utils.CaseInsensitiveString(cls.name) for cls in btclients.clients()]


# Argument types should match metavar names and raise ValueError

def NUMBER(string):
    return int(string)

def TIMESTAMP(string):
    return utils.timestamp.parse(string)

def DB(string):
    if string in DB_NAMES:
        return string.casefold()
    else:
        raise ValueError(f'Unsupported databasae: {string}')

def TRACKER(string):
    if string in TRACKER_NAMES:
        return string.casefold()
    else:
        raise ValueError(f'Unsupported tracker: {string}')

def CLIENT(string):
    if string in BTCLIENT_NAMES:
        return string.casefold()
    else:
        raise ValueError(f'Unsupported client: {string}')

def IMAGEHOST(string):
    if string in IMGHOST_NAMES:
        return string.casefold()
    else:
        raise ValueError(f'Unsupported image hosting service: {string}')


def OPTION(string):
    if string in constants.OPTION_PATHS:
        return string.casefold()
    else:
        raise ValueError(f'Unknown option: {string}')


def parse(args):
    """
    Parse CLI arguments

    :param args: Sequence of strings (`sys.argv[1:]`)

    :return: :class:`argparse.Namespace` instance
    """
    parser = argparse.ArgumentParser(
        description='Collect metadata for uploading content to private trackers',
        formatter_class=MyHelpFormatter,
    )
    parser.add_argument('--version',
                        action='version',
                        version=f'{__project_name__} {__version__}')
    parser.add_argument('--debug', '-d',
                        metavar='FILE',
                        help='Write debugging messages to FILE')
    parser.add_argument('--trackers-file', '-t',
                        help='Tracker configuration file path',
                        default=constants.TRACKERS_FILEPATH)
    parser.add_argument('--clients-file', '-c',
                        help='BitTorrent client configuration file path',
                        default=constants.CLIENTS_FILEPATH)
    parser.add_argument('--ignore-cache', '-ic',
                        help='Ignore existing files and information from previous calls',
                        action='store_true')

    subparsers = parser.add_subparsers(title='commands')
    mutex_groups = {}

    def add_subcmd(command, names, info='', args={}):
        description = textwrap.dedent(command.__doc__.strip('\n'))
        if info:
            description += f'\n\n{info}'
        help = description.split('\n', 1)[0]
        parser = subparsers.add_parser(
            names[0],
            aliases=names[1:],
            help=help,
            description=description,
            formatter_class=MyHelpFormatter,
        )
        parser.set_defaults(subcmd=command)

        for argname, argopts in args.items():
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
                parser.add_argument(*names, **argopts)

    # Command: id
    add_subcmd(
        command=commands.search_db,
        names=('id',),
        args={
            'DB': {
                'type': DB,
                'help': ('Case-insensitive database name.\n'
                         'Supported databases: ' + ', '.join(DB_NAMES)),
            },
            'CONTENT': {'help': 'Path to release content'},
        },
    )

    # Command: release-name
    add_subcmd(
        command=commands.release_name,
        names=('release-name', 'rn'),
        args={
            'CONTENT': {'help': 'Path to release content'},
        },
    )

    # Command: create-torrent
    add_subcmd(
        command=commands.create_torrent,
        names=('create-torrent', 'ct'),
        args={
            'TRACKER': {
                'type': TRACKER,
                'help': ('Case-insensitive tracker name.\n'
                         'Supported trackers: ' + ', '.join(TRACKER_NAMES)),
            },
            'CONTENT': {'help': 'Path to release content'},
            ('--add-to', '-a'): {
                'type': CLIENT,
                'metavar': 'CLIENT',
                'help': ('Add the created torrent to a running BitTorrent client instance.\n'
                         'Supported clients: ' + ', '.join(BTCLIENT_NAMES)),
            },
            ('--copy-to', '-c'): {
                'metavar': 'DIRECTORY',
                'help': 'Copy the created torrent to DIRECTORY',
            },
        },
    )

    # Command: add-torrent
    add_subcmd(
        command=commands.add_torrent,
        names=('add-torrent', 'at'),
        args={
            'CLIENT': {
                'type': CLIENT,
                'help': ('Case-insensitive client name.\n'
                         'Supported clients: ' + ', '.join(BTCLIENT_NAMES)),
            },
            'TORRENT': {
                'nargs': '+',
                'help': 'Path to torrent file',
            },
            ('--download-path', '-p'): {
                'help': "Parent directory of the torrent's content",
                'metavar': 'DIRECTORY',
            },
        },
    )

    # Command: screenshots
    add_subcmd(
        command=commands.screenshots,
        names=('screenshots', 'ss'),
        args={
            'CONTENT': {'help': 'Path to release content'},
            ('--timestamps', '-t'): {
                'nargs': '+',
                'default': (),
                'type': TIMESTAMP,
                'metavar': 'TIMESTAMP',
                'help': 'Space-separated list of [[HH:]MM:]SS strings',
            },
            ('--number', '-n'): {
                'type': NUMBER,
                'help': 'How many screenshots to make in total',
                'default': 0,
            },
            ('--upload-to', '-u'): {
                'type': IMAGEHOST,
                'metavar': 'IMAGEHOST',
                'help': ('Upload screenshots to image hosting service.\n'
                         'Supported services: ' + ', '.join(IMGHOST_NAMES)),
            },
        }
    )

    # Command: upload-images
    add_subcmd(
        command=commands.upload_images,
        names=('upload-images', 'ui'),
        args={
            'IMAGEHOST': {
                'type': IMAGEHOST,
                'help': ('Case-insensitive name of image hosting service.\n'
                         'Supported services: ' + ', '.join(IMGHOST_NAMES)),
            },
            'IMAGE': {
                'nargs': '+',
                'help': 'Path to image file',
            },
        },
    )

    # Command: mediainfo
    add_subcmd(
        command=commands.mediainfo,
        names=('mediainfo', 'mi'),
        args={
            'CONTENT': {'help': 'Path to release content'},
        },
    )

    # Command: submit
    add_subcmd(
        command=commands.submit,
        names=('submit',),
        args={
            'TRACKER': {
                'type': TRACKER,
                'help': ('Case-insensitive tracker name.\n'
                         'Supported trackers: ' + ', '.join(TRACKER_NAMES)),
            },
            'CONTENT': {'help': 'Path to release content'},
            ('--add-to', '-a'): {
                'type': CLIENT,
                'metavar': 'CLIENT',
                'help': ('Add the created torrent to a running BitTorrent client instance.\n'
                         'Supported clients: ' + ', '.join(BTCLIENT_NAMES)),
            },
            ('--copy-to', '-c'): {
                'metavar': 'DIRECTORY',
                'help': 'Copy the created torrent to DIRECTORY',
            },
        },
    )

    # Command: set
    add_subcmd(
        command=commands.set,
        names=('set',),
        info='options:\n  ' + '\n  '.join(o for o in constants.OPTION_PATHS),
        args={
            'OPTION': {
                'type': OPTION,
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
        },
    )

    if args is None:
        parsed = parser.parse_args()
    else:
        parsed = parser.parse_args(args)

    if not hasattr(parsed, 'subcmd'):
        parser.print_help()
        sys.exit(0)
    else:
        return parsed


class MyHelpFormatter(argparse.HelpFormatter):
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
        return [line
                for paragraph in text.split('\n')
                for line in wrap(paragraph)]
