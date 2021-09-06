"""
Entry point
"""

import asyncio
import sys

from ... import (__homepage__, __project_name__, application_setup,
                 application_shutdown, errors)
from ...utils import update
from . import commands, utils


def main(args=None):
    sys.exit(_main(args))


def _main(args=None):
    aioloop = asyncio.get_event_loop()
    get_newer_version_task = None

    try:
        if utils.is_tty():
            from .tui import TUI
            ui = TUI()
            # Find latest version and generate update message in a background task
            get_newer_version_task = aioloop.create_task(update.get_newer_version())
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

        # Print update message if there is a newer version available
        if get_newer_version_task:
            try:
                # don't wait for get_newer_version_task to prevent annoying wait
                # times before the user gets their prompt back.
                newer_version = aioloop.run_until_complete(
                    asyncio.wait_for(get_newer_version_task, timeout=0)
                )
            except (asyncio.TimeoutError, errors.RequestError):
                pass
            else:
                if newer_version:
                    msg = f'New {__project_name__} version available: {newer_version}'
                    print(msg, file=sys.stderr)

        return exit_code
