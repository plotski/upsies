import os

from .. import errors
from ..utils import LazyModule

import logging  # isort:skip
_log = logging.getLogger(__name__)

subprocess = LazyModule(module='subprocess', namespace=globals())
shlex = LazyModule(module='shlex', namespace=globals())


_run_output_cache = {}

def run(argv, ignore_errors=False, join_stderr=False, cache=False):
    """
    Execute subprocess

    :param argv: Command to execute
    :type argv: list of str
    :param bool ignore_errors: Do not raise `ProcessError` if stderr is non-empty
    :param bool join_stderr: Redirect stderr to stdout
    :param bool cache: Cache output based on `argv`

    :raise DependencyError: if the command fails to execute
    :raise ProcessError: if stdout is not empty and `ignore_errors` is `False`

    :return: stdout from process
    :rtype: str
    """
    argv = tuple(str(arg) for arg in argv)
    if cache and argv in _run_output_cache:
        stdout, stderr = _run_output_cache[argv]
    else:
        stdout = subprocess.PIPE
        if join_stderr:
            stderr = subprocess.STDOUT
        else:
            stderr = subprocess.PIPE
        try:
            _log.debug('Running: %s', ' '.join(shlex.quote(arg) for arg in argv))
            proc = subprocess.run(argv,
                                  shell=False,
                                  encoding='utf-8',
                                  stdout=stdout,
                                  stderr=stderr)
        except OSError:
            raise errors.DependencyError(f'Missing dependency: {os.path.basename(argv[0])}')
        else:
            stdout, stderr = proc.stdout, proc.stderr
            if cache:
                _run_output_cache[argv] = (proc.stdout, proc.stderr)
    if stderr and not ignore_errors:
        raise errors.ProcessError(stderr)
    return stdout
