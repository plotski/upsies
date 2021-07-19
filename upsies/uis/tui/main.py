"""
Entry point
"""

import sys

from ... import __homepage__, application_setup, application_shutdown, errors
from . import commands, utils


def main(args=None):
    sys.exit(_main(args))


def _main(args=None):
    if sys.argv[1] == 'wtf':
        _wtf()
        exit(0)

    try:
        if utils.is_tty():
            from .tui import TUI
            ui = TUI()
        else:
            from .headless import Headless
            ui = Headless()

        cmd = commands.run(args)
        application_setup(cmd.config)
        exit_code = ui.run(cmd.jobs_active)
        application_shutdown(cmd.config)

    # UI was terminated by user prematurely
    except errors.CancelledError as e:
        print(e, file=sys.stderr)
        return 1

    except (errors.UiError, errors.DependencyError, errors.ContentError) as e:
        print(e, file=sys.stderr)
        return 1

    except Exception as e:
        # Unexpected exception; expected exceptions are handled by JobBase child
        # classes by calling their error() or exception() methods.
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
        print()

        # Exceptions from subprocesses should save their traceback.
        # See errors.SubprocessError.
        if hasattr(e, 'original_traceback'):
            print(e.original_traceback)
            print()

        print(f'Please report the traceback above as a bug: {__homepage__}', file=sys.stderr)
        return 1

    else:
        # Print last job's output to stdout for use in output redirection.
        # Ignore disabled jobs.
        if exit_code == 0:
            for j in reversed(cmd.jobs_active):
                if j.is_enabled:
                    if j.output:
                        print('\n'.join(j.output))
                    break

        return exit_code


def _wtf():
    import os
    from ... import utils

    print('$PATH:', os.environ['PATH'].split(':'))
    for path in os.environ['PATH'].split(':'):
        mipath = os.path.join(path, 'mediainfo')
        print('Looking for mediainfo in', path)
        if os.path.exists(mipath):
            print('mediainfo found: ', mipath)
            break
    else:
        print('No mediainfo found!')
        exit(1)

    print('##################################################')

    micmd = ('mediainfo', '--version')
    print(f'Running: {micmd}:')
    print(utils.subproc.run(micmd))

    print('##################################################')

    micmd = ('mediainfo', '--Output=JSON', sys.argv[2])
    print(f'Running: {micmd}:')
    print(utils.subproc.run(micmd))

    print('##################################################')

    print(f'Running: utils.video._run_mediainfo({sys.argv[2]!r}, \'--Output=JSON\'):')
    print(utils.video._run_mediainfo(sys.argv[2], '--Output=JSON'))

    print('##################################################')

    print(f'Running: utils.video._run_mediainfo({sys.argv[2]!r}, \'--Output=JSON\'):')
    print(utils.video._run_mediainfo(sys.argv[2], '--Output=JSON'))

    print('##################################################')

    print(f'Running: utils.video._tracks({sys.argv[2]!r}):')
    print(utils.video._tracks(sys.argv[2]))

    print('##################################################')

    print(f'Running: utils.video.tracks({sys.argv[2]!r}):')
    print(utils.video.tracks(sys.argv[2]))

    print('##################################################')

    print(f'Running: utils.video.default_track({sys.argv[2]!r}):')
    print(utils.video.default_track('video', sys.argv[2]))

    print('##################################################')

    print(f'Running: utils.video.width({sys.argv[2]!r}):')
    print(utils.video.width(sys.argv[2]))

    print('##################################################')

    print(f'Running: utils.video.audio_format({sys.argv[2]!r}):')
    print(utils.video.audio_format(sys.argv[2]))

    
