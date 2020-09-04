import argparse
import os
import sys

from xdg.BaseDirectory import xdg_config_home as XDG_CONFIG_HOME

from ... import __project_name__, utils
from . import subcmds

import logging  # isort:skip
_log = logging.getLogger(__name__)

_config_filepath = os.path.join(XDG_CONFIG_HOME, 'upsies', 'config.ini')


def parse(args):
    parser = argparse.ArgumentParser(usage=f'{__project_name__} [command] [options]',
                                     formatter_class=MyHelpFormatter)
    parser.add_argument('--debug', '-d',
                        help='Print debugging messages',
                        action='store_true')
    parser.add_argument('--configfile', '-c',
                        help='Configuration file path',
                        default=_config_filepath)
    parser.add_argument('--ignore-cache', '-ic',
                        help='Do not use previously gathered information',
                        action='store_true')
    parser.add_argument('--tracker', '-t',
                        help='Tracker name',
                        default=None)

    subparsers = parser.add_subparsers(title='subcommands', metavar='')

    release_name = subparsers.add_parser(
        'release-name', aliases=('rn',), help='Create normalized release name',
        description=('Print the full release name properly formatted to stdout.\n\n'
                     'IMDb is searched to get the correct title and an AKA if applicable. '
                     'Audio and video information is detected with mediainfo. '
                     'Missing required information is highlighted with placeholders, '
                     'e.g. "UNKNOWN_RESOLUTION".'),
        formatter_class=MyHelpFormatter,
    )
    release_name.add_argument('path', help='Path to release content')
    release_name.set_defaults(subcmd=subcmds.release_name)

    imdb = subparsers.add_parser('imdb', help='Find IMDb ID', formatter_class=MyHelpFormatter)
    imdb.add_argument('path', help='Path to release content')
    imdb.set_defaults(subcmd=subcmds.make_search_command('imdb'))

    tmdb = subparsers.add_parser('tmdb', help='Find TMDB ID', formatter_class=MyHelpFormatter)
    tmdb.add_argument('path', help='Path to release content')
    tmdb.set_defaults(subcmd=subcmds.make_search_command('tmdb'))

    tvmaze = subparsers.add_parser('tvmaze', help='Find TVmaze ID', formatter_class=MyHelpFormatter)
    tvmaze.add_argument('path', help='Path to release content')
    tvmaze.set_defaults(subcmd=subcmds.make_search_command('tvmaze'))

    screenshots = subparsers.add_parser(
        'screenshots', aliases=('ss',),
        help='Create screenshots',
        description='Wrapper around ffmpeg that dumps frames into PNG images.',
        formatter_class=MyHelpFormatter,
    )
    screenshots.add_argument('path', help='Path to release content')
    screenshots.add_argument(
        '--timestamps', '-t',
        help='Space-separated list of [HH:]MM:SS strings',
        metavar='TIMESTAMP',
        default=(),
        nargs='+',
        type=Timestamp,
    )
    screenshots.add_argument(
        '--number', '-n',
        help='How many screenshots to make (including those specified by --timestamps)',
        type=Number,
        default=0,
    )
    screenshots.add_argument(
        '--upload-to', '-u',
        help='Upload screenshots to image hosting service',
        metavar='SERVICE',
    )
    screenshots.set_defaults(subcmd=subcmds.screenshots)

    torrent = subparsers.add_parser('torrent', help='Create torrent file', formatter_class=MyHelpFormatter)
    torrent.add_argument('path', help='Path to release content')
    torrent.set_defaults(subcmd=subcmds.torrent)
    torrent.add_argument(
        '--add-to', '-a',
        help='Add created torrent to a running BitTorrent client instance',
        metavar='CLIENT',
    )
    torrent.add_argument(
        '--copy-to', '-c',
        help='Copy created torrent to directory PATH',
        metavar='PATH',
    )

    submit = subparsers.add_parser(
        'submit',
        help='Gather all metadata and upload to tracker',
        formatter_class=MyHelpFormatter,
    )
    submit.add_argument('path', help='Path to release content')
    submit.set_defaults(subcmd=subcmds.submit)

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
    try:
        return utils.timestamp.parse(string)
    except ValueError as e:
        raise argparse.ArgumentTypeError(e)


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
