import argparse
import functools
import sys

from ... import __project_name__, defaults, utils
from ...jobs import submit as trackers
from ...tools import client as clients
from ...tools import imghost as imghosts
from . import subcmds

import logging  # isort:skip
_log = logging.getLogger(__name__)


def parse(args):
    parser = argparse.ArgumentParser(usage=f'{__project_name__} [command] [options]',
                                     formatter_class=MyHelpFormatter)
    parser.add_argument('--debug', '-d',
                        help='Print debugging messages',
                        action='store_true')
    parser.add_argument('--trackers-file', '-t',
                        help='Tracker configuration file path',
                        default=defaults.trackers_filepath)
    parser.add_argument('--clients-file', '-c',
                        help='BitTorrent client configuration file path',
                        default=defaults.clients_filepath)
    parser.add_argument('--ignore-cache', '-ic',
                        help='Do not use previously gathered information',
                        action='store_true')

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
        type=TIMESTAMP,
        help='Space-separated list of [[HH:]MM:]SS strings',
        metavar='TIMESTAMP',
        default=(),
        nargs='+',
    )
    screenshots.add_argument(
        '--number', '-n',
        type=NUMBER,
        help='How many screenshots to make in total',
        default=0,
    )
    screenshots.add_argument(
        '--upload-to', '-u',
        type=IMGHOST,
        help=('Upload screenshots to image hosting service.\n'
              'Supported services: ' + ', '.join(_get_names(imghosts, 'Uploader', 'name'))),
        metavar='IMGHOST',
    )

    mediainfo = subparsers.add_parser(
        'mediainfo', aliases=('mi',),
        help='Print mediainfo output',
        description=('If PATH is a directory, it is recursively searched '
                     'for the first video file in natural order, '
                     'i.e. "File1.mp4" comes before "File10.mp4".\n\n'
                     'Any irrelevant parts in the file path are removed from the output.'),
        formatter_class=MyHelpFormatter,
    )
    mediainfo.set_defaults(subcmd=subcmds.mediainfo)
    mediainfo.add_argument('path', help='Path to release content')

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
        'tracker',
        type=TRACKER,
        help=('Case-insensitive tracker name.\n'
              'Supported trackers: ' + ', '.join(_get_names(trackers, 'SubmissionJob', 'trackername'))),
    )
    torrent.add_argument(
        '--add-to', '-a',
        type=CLIENT,
        help=('Add the created torrent to a running BitTorrent client instance.\n'
              'Supported clients: ' + ', '.join(_get_names(clients, 'ClientApi', 'name'))),
        metavar='CLIENT',
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
    submit.add_argument(
        'tracker',
        type=TRACKER,
        help=('Case-insensitive tracker name.\n'
              'Supported trackers: ' + ', '.join(_get_names(trackers, 'SubmissionJob', 'trackername'))),
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
    if string in _get_names(clients, 'ClientApi', 'name'):
        return string.casefold()
    else:
        raise ValueError(f'Unsupported client: {string}')

def IMGHOST(string):
    if string in _get_names(imghosts, 'Uploader', 'name'):
        return string.casefold()
    else:
        raise ValueError(f'Unsupported image hosting service: {string}')


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
def _get_names(module, clsname, name_attribute):
    """Return attribute values of classes from public submodules within `module`"""
    import inspect
    modules = (module for name, module in inspect.getmembers(module, inspect.ismodule)
               if not name.startswith('_'))
    clsses = [getattr(module, clsname) for module in modules]
    return [utils.CaseInsensitiveString(getattr(cls, name_attribute))
            for cls in clsses]
