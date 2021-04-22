"""
Entry point
"""

import sys

from ... import __homepage__, application_setup, application_shutdown, errors
from . import commands
from .ui import UI

import logging  # isort:skip
_log = logging.getLogger(__name__)


def main(args=None):
    sys.exit(_main(args))


def _main(args=None):
    try:
        ui = UI()
        cmd = commands.run(args)
        application_setup(cmd.config)
        exit_code = ui.run(cmd.jobs_active)
        application_shutdown(cmd.config)

    # TUI was terminated by user prematurely
    except errors.CancelledError as e:
        print(e, file=sys.stderr)
        return 1

    except errors.DependencyError as e:
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
