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
    args = parse_args(args)
    if args.debug:
        logging.basicConfig(
            format='%(asctime)s: %(name)s: %(message)s',
            filename=args.debug,
        )
        logging.getLogger(__project_name__).setLevel(level=logging.DEBUG)

    try:
        cfg = config.Config(defaults=defaults.config)
        cfg.read('trackers', filepath=args.trackers_file, ignore_missing=True)
        cfg.read('clients', filepath=args.clients_file, ignore_missing=True)
    except errors.ConfigError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    exit_code = 99
    try:
        cmd = args.subcmd(args=args, config=cfg)
        assert isinstance(cmd, CommandBase)
        ui = UI(jobs=cmd.jobs)
        exit_code = ui.run()
    except (errors.ConfigError, errors.DependencyError, errors.NoContentError) as e:
        print(e, file=sys.stderr)
        exit_code = 1
    except Exception as e:
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
        print()
        print(f'Please report the traceback above as a bug: {__homepage__}', file=sys.stderr)
        exit_code = 1
    else:
        # Print last job's output to stdout
        if exit_code == 0:
            final_job = cmd.jobs[-1]
            if final_job.output:
                print('\n'.join(final_job.output))
    finally:
        _log.debug('UI terminated')
        return exit_code
