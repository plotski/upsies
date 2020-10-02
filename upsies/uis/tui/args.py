import argparse
import functools
import sys

from ... import __project_name__, __version__, defaults, utils
from ...jobs import submit as trackers
from ...tools import btclient as btclients
from ...tools import imghost as imghosts
from ...tools import dbs
from . import subcmds

import logging  # isort:skip
_log = logging.getLogger(__name__)


def parse(args):
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
                        default=defaults.trackers_filepath)
    parser.add_argument('--clients-file', '-c',
                        help='BitTorrent client configuration file path',
                        default=defaults.clients_filepath)
    parser.add_argument('--ignore-cache', '-ic',
                        help='Ignore existing files and information from previous calls',
                        action='store_true')

    db_names = ', '.join(_get_names(dbs, '', 'label'))
    tracker_names = ', '.join(_get_names(trackers, 'SubmissionJob', 'trackername'))
    imghost_names = ', '.join(_get_names(imghosts, 'Uploader', 'name'))
    btclient_names = ', '.join(_get_names(btclients, 'ClientApi', 'name'))

    subparsers = parser.add_subparsers(title='commands')

    def add_subcmd(handler, names, help, description='', args={}):
        parser = subparsers.add_parser(
            names[0],
            aliases=names[1:],
            help=help,
            description=description,
            formatter_class=MyHelpFormatter,
        )
        parser.set_defaults(subcmd=handler)
        for argname,argopts in args.items():
            names = (argname,) if isinstance(argname, str) else argname
            parser.add_argument(*names, **argopts)

    # Command: id
    add_subcmd(
        handler=subcmds.search_db,
        names=('id',),
        help='Pick ID from search results from IMDb, TMDb, etc',
        args={
            'DB': {
                'type': DB,
                'help': ('Case-insensitive database name.\n'
                         'Supported databases: ' + db_names),
            },
            'CONTENT': {'help': 'Path to release content'},
        },
    )

    # Command: release-name
    add_subcmd(
        handler=subcmds.release_name,
        names=('release-name', 'rn'),
        help='Create standardized release name',
        description=('Print the properly formatted release name.\n\n'
                     'IMDb is searched to get the correct title, year and alternative '
                     'title if applicable. Audio and video information is detected with '
                     'mediainfo. Missing required information is highlighted with '
                     'placeholders, e.g. "UNKNOWN_RESOLUTION".'),
        args={
            'CONTENT': {'help': 'Path to release content'},
        },
    )

    # Command: create-torrent
    add_subcmd(
        handler=subcmds.create_torrent,
        names=('create-torrent', 'ct'),
        help='Create torrent file and optionally add it to a client',
        description='Create torrent for a specific tracker.',
        args={
            'TRACKER': {
                'type': TRACKER,
                'help': ('Case-insensitive tracker name.\n'
                         'Supported trackers: ' + tracker_names),
            },
            'CONTENT': {'help': 'Path to release content'},
            ('--add-to', '-a'): {
                'type': CLIENT,
                'metavar': 'CLIENT',
                'help': ('Add the created torrent to a running BitTorrent client instance.\n'
                         'Supported clients: ' + btclient_names),
            },
            ('--copy-to', '-c'): {
                'metavar': 'DIRECTORY',
                'help': 'Copy the created torrent to DIRECTORY',
            },
        },
    )

    # Command: add-torrent
    add_subcmd(
        handler=subcmds.add_torrent,
        names=('add-torrent', 'at'),
        help='Send torrent file to BitTorrent Client',
        args={
            'CLIENT': {
                'type': CLIENT,
                'help': ('Case-insensitive client name.\n'
                         'Supported clients: ' + btclient_names),
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
        handler=subcmds.screenshots,
        names=('screenshots', 'ss'),
        help='Create and optionally upload screenshots',
        description=('Create PNG screenshots with ffmpeg and optionally '
                     'upload them to an image hosting service.'),
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
                         'Supported services: ' + imghost_names),
            },
        }
    )

    # Command: upload-images
    add_subcmd(
        handler=subcmds.upload_images,
        names=('upload-images', 'ui'),
        help='Upload image to image hosting service',
        args={
            'IMAGEHOST': {
                'type': IMAGEHOST,
                'help': ('Case-insensitive name of image hosting service.\n'
                         'Supported services: ' + imghost_names),
            },
            'IMAGE': {
                'nargs': '+',
                'help': 'Path to image file',
            },
        },
    )

    # Command: mediainfo
    add_subcmd(
        handler=subcmds.mediainfo,
        names=('mediainfo', 'mi'),
        help='Print mediainfo output',
        description=('If PATH is a directory, it is recursively searched for the first video '
                     'file in natural order, i.e. "File1.mp4" comes before "File10.mp4".\n\n'
                     'Any irrelevant parts in the file path are removed from the output.'),
        args={
            'CONTENT': {'help': 'Path to release content'},
        },
    )

    # Command: submit
    add_subcmd(
        handler=subcmds.submit,
        names=('submit',),
        help='Gather all required metadata and upload PATH to tracker',
        args={
            'TRACKER': {
                'type': TRACKER,
                'help': ('Case-insensitive tracker name.\n'
                         'Supported trackers: ' + tracker_names),
            },
            'CONTENT': {'help': 'Path to release content'},
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


# Type names should match metavar names and raise ValueError

def NUMBER(string):
    return int(string)

def TIMESTAMP(string):
    return utils.timestamp.parse(string)

def TRACKER(string):
    if string in _get_names(trackers, 'SubmissionJob', 'trackername'):
        return string.casefold()
    else:
        raise ValueError(f'Unsupported tracker: {string}')

def CLIENT(string):
    if string in _get_names(btclients, 'ClientApi', 'name'):
        return string.casefold()
    else:
        raise ValueError(f'Unsupported client: {string}')

def IMAGEHOST(string):
    if string in _get_names(imghosts, 'Uploader', 'name'):
        return string.casefold()
    else:
        raise ValueError(f'Unsupported image hosting service: {string}')

def DB(string):
    if string in _get_names(dbs, '', 'label'):
        return string.casefold()
    else:
        raise ValueError(f'Unsupported databasae: {string}')


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
                import textwrap
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

