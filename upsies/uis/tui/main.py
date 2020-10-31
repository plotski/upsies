import sys

from ... import __homepage__, __project_name__, config, defaults, errors
from .args import parse as parse_args
from .commands import CommandBase
from .ui import UI

import logging  # isort:skip
_log = logging.getLogger(__name__)


def main(args=None):
    sys.exit(_main(args))


def _main(args=None):
    # Read CLI arguments
    # argparse has sys.exit(2) hardcoded for CLI errors.
    try:
        args = parse_args(args)
    except SystemExit:
        return 1

    if args.debug:
        logging.basicConfig(
            format='%(asctime)s: %(name)s: %(message)s',
            filename=args.debug,
        )
        logging.getLogger(__project_name__).setLevel(level=logging.DEBUG)

    # Read config files
    try:
        cfg = config.Config(defaults=defaults.config)
        cfg.read('trackers', filepath=args.trackers_file, ignore_missing=True)
        cfg.read('clients', filepath=args.clients_file, ignore_missing=True)
    except errors.ConfigError as e:
        print(e, file=sys.stderr)
        return 1

    # Run UI
    try:
        cmd = args.subcmd(args=args, config=cfg)
        assert isinstance(cmd, CommandBase)
        ui = UI(jobs=cmd.jobs_active)
        exit_code = ui.run()

    # Some errors are expected
    except (errors.ConfigError, errors.DependencyError, errors.NoContentError) as e:
        print(e, file=sys.stderr)
        return 1

    # TUI was terminated by user prematurely
    except errors.CancelledError as e:
        print(e, file=sys.stderr)
        return 1

    except BaseException as e:
        # Unexpected exception; expected exceptions are handled by JobBase child
        # classes by calling their error() or exception() methods.
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
        print()

        # Exceptions from subprocesses should save their traceback
        if hasattr(e, 'original_traceback'):
            print(e.original_traceback)
            print()

        print(f'Please report the traceback above as a bug: {__homepage__}', file=sys.stderr)
        return 1

    else:
        # Print last job's output to stdout
        if exit_code == 0:
            final_job = cmd.jobs_active[-1]
            if final_job.output:
                print('\n'.join(final_job.output))

        return exit_code
