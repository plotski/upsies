"""
Entry point
"""

import sys

from ... import __homepage__, cleanup, errors
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
        exit_code = ui.run(cmd.jobs_active)
        cleanup.cleanup(cmd.config)

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
        # Print last job's output to stdout for use in output redirection
        if exit_code == 0:
            final_job = cmd.jobs_active[-1]
            if final_job.output:
                print('\n'.join(final_job.output))
        return exit_code
