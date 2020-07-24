import contextlib
import sys

from ... import __homepage__, __project_name__, config, errors
from .args import parse as parse_args
from .subcmds import SubcommandBase
from .ui import UI

import logging  # isort:skip
_log = logging.getLogger(__name__)


def main(args=None):
    sys.exit(_main(args))


def _main(args=None):
    args = parse_args(args)
    if args.debug:
        logging.basicConfig(format='%(asctime)s: %(name)s: %(message)s')
        logging.getLogger(__project_name__).setLevel(level=logging.DEBUG)
        logging.getLogger('prompt_toolkit').setLevel(level=logging.DEBUG)

    try:
        cfg = config.Config(args.configfile)
    except errors.ConfigError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    try:
        cmd = args.subcmd(args=args, config=cfg)
        assert isinstance(cmd, SubcommandBase)
        ui = UI(jobs=cmd.jobs)
        with _log_to_buffer(ui.log.buffer):
            exit_code = ui.run()
    except (errors.ConfigError, errors.DependencyError) as e:
        print(e, file=sys.stderr)
        exit_code = 1
    except Exception as e:
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
        print()
        print(f'Please report the traceback above as a bug: {__homepage__}')
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


@contextlib.contextmanager
def _log_to_buffer(buffer):
    """
    Context manager that redirects `logging` output

    :param buffer: :class:`Buffer` instance
    """

    class LogRecordHandler(logging.Handler):
        def emit(self, record, _buffer=buffer):
            msg = f'{self.format(record)}\n'
            _buffer.insert_text(msg, fire_event=False)

    # Stash original log handlers
    root_logger = logging.getLogger()
    original_handlers = []
    for h in tuple(root_logger.handlers):
        original_handlers.append(h)
        root_logger.removeHandler(h)

    if original_handlers:
        # Install new log handler with original formatter
        handler = LogRecordHandler()
        original_formatter = original_handlers[0].formatter
        handler.setFormatter(original_formatter)
        root_logger.addHandler(handler)
        _log.debug('Redirected logging')

    # Run application
    yield

    if original_handlers:
        # Restore original handlers
        root_logger.handlers.remove(handler)
        for h in original_handlers:
            root_logger.addHandler(h)
        _log.debug('Restored logging')
