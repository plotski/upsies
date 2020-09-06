import argparse
import functools
import os
import sys

from xdg.BaseDirectory import xdg_config_home as XDG_CONFIG_HOME

from ... import __project_name__, utils
from ...tools import client, imghost
from . import subcmds

import logging  # isort:skip
_log = logging.getLogger(__name__)

_main_config_filepath = os.path.join(XDG_CONFIG_HOME, 'upsies', 'config.ini')
_trackers_config_filepath = os.path.join(XDG_CONFIG_HOME, 'upsies', 'trackers.ini')
_clients_config_filepath = os.path.join(XDG_CONFIG_HOME, 'upsies', 'clients.ini')


def parse(args):
    parser = argparse.ArgumentParser(usage=f'{__project_name__} [command] [options]',
                                     formatter_class=MyHelpFormatter)
    parser.add_argument('--debug', '-d',
                        help='Print debugging messages',
                        action='store_true')
    parser.add_argument('--trackers-file', '-t',
                        help='Tracker configuration file path',
                        default=_trackers_config_filepath)
    parser.add_argument('--clients-file', '-c',
                        help='BitTorrent client configuration file path',
                        default=_clients_config_filepath)
    parser.add_argument('--ignore-cache', '-ic',
                        help='Do not use previously gathered information',
                        action='store_true')
    parser.add_argument('--tracker', '-t',
                        help='Tracker name',
                        default=None)

    subparsers = parser.add_subparsers(title='commands')

    release_name = subparsers.add_parser(
        'release-name', aliases=('rn',),
        help='Create standardized release name',
        description=('Print the full release name properly formatted to stdout.\n\n'
                     'IMDb is searched to get the correct title and an AKA if applicable. '
                     'Audio and video information is detected with mediainfo. '
                     'Missing required information is highlighted with placeholders, '
                     'e.g. "UNKNOWN_RESOLUTION".'),
        formatter_class=MyHelpFormatter,
    )
    release_name.set_defaults(subcmd=subcmds.release_name)
    release_name.add_argument('path', help='Path to release content')

    imdb = subparsers.add_parser(
        'imdb',
        help='Pick IMDb ID from search results',
        formatter_class=MyHelpFormatter,
    )
    imdb.set_defaults(subcmd=subcmds.make_search_command('imdb'))
    imdb.add_argument('path', help='Path to release content')

    tmdb = subparsers.add_parser(
        'tmdb',
        help='Pick TMDb ID from search results',
        formatter_class=MyHelpFormatter,
    )
    tmdb.set_defaults(subcmd=subcmds.make_search_command('tmdb'))
    tmdb.add_argument('path', help='Path to release content')

    tvmaze = subparsers.add_parser(
        'tvmaze',
        help='Pick TVmaze ID from search results',
        formatter_class=MyHelpFormatter,
    )
    tvmaze.set_defaults(subcmd=subcmds.make_search_command('tvmaze'))
    tvmaze.add_argument('path', help='Path to release content')

    screenshots = subparsers.add_parser(
        'screenshots', aliases=('ss',),
        help='Create and optionally upload screenshots',
        description=('Create PNG screenshots with ffmpeg and optionally '
                     'upload them to an image hosting service.'),
        formatter_class=MyHelpFormatter,
    )
    screenshots.set_defaults(subcmd=subcmds.screenshots)
    screenshots.add_argument('path', help='Path to release content')
    screenshots.add_argument(
        '--timestamps', '-t',
        help='Space-separated list of [[HH:]MM:]SS strings',
        metavar='TIMESTAMP',
        default=(),
        nargs='+',
        type=Timestamp,
    )
    screenshots.add_argument(
        '--number', '-n',
        help='How many screenshots to make in total',
        type=Number,
        default=0,
    )
    screenshots.add_argument(
        '--upload-to', '-u',
        help=('Upload screenshots to image hosting service.\n'
              'Supported services are: ' + ', '.join(_get_names(imghost, 'Uploader'))),
        metavar='SERVICE',
        choices=_get_names(imghost, 'Uploader'),
    )

    torrent = subparsers.add_parser(
        'torrent', aliases=('tor',),
        help='Create torrent file',
        description=('Create torrent for a specific tracker with all the appropriate '
                     'requirements like a "source" field.'),
        formatter_class=MyHelpFormatter,
    )
    torrent.set_defaults(subcmd=subcmds.torrent)
    torrent.add_argument('path', help='Path to release content')
    torrent.add_argument(
        '--add-to', '-a',
        help=('Add the created torrent to a running BitTorrent client instance.\n'
              'Supported clients are: ' + ', '.join(_get_names(client, 'ClientApi'))),
        metavar='CLIENT',
        choices=_get_names(client, 'ClientApi'),
    )
    torrent.add_argument(
        '--copy-to', '-c',
        help='Copy the created torrent to directory PATH',
        metavar='PATH',
    )

    submit = subparsers.add_parser(
        'submit',
        help='Gather all required metadata and upload PATH to tracker',
        formatter_class=MyHelpFormatter,
    )
    submit.set_defaults(subcmd=subcmds.submit)
    submit.add_argument('path', help='Path to release content')

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

def Number(string):
    return int(string)

def Timestamp(string):
    return utils.timestamp.parse(string)


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
def _get_names(module, clsname):
    """Return list `module.submodule.clsname.name` values for each public submodule"""
    import inspect
    modules = (module for name, module in inspect.getmembers(module, inspect.ismodule)
               if not name.startswith('_'))
    return [getattr(module, clsname).name for module in modules]
