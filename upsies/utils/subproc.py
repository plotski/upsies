"""
Execute external commands
"""

import os

from .. import errors
from ..utils import LazyModule

import logging  # isort:skip
_log = logging.getLogger(__name__)

subprocess = LazyModule(module='subprocess', namespace=globals())
shlex = LazyModule(module='shlex', namespace=globals())

_command_output_cache = {}


def run(argv, ignore_errors=False, join_stderr=False, cache=False):
    """
    Execute command in subprocess

    :param argv: Command to execute
    :type argv: list of str
    :param bool ignore_errors: Do not raise :class:`.ProcessError` if stderr is
        non-empty
    :param bool join_stderr: Redirect stderr to stdout
    :param bool cache: Cache output based on `argv`

    :raise DependencyError: if the command fails to execute
    :raise ProcessError: if stdout is not empty and `ignore_errors` is `False`

    :return: Output from process
    :rtype: str
    """
    argv = tuple(str(arg) for arg in argv)
    if cache and argv in _command_output_cache:
        stdout, stderr = _command_output_cache[argv]
    else:
        fh_stdout = subprocess.PIPE
        if join_stderr:
            fh_stderr = subprocess.STDOUT
        else:
            fh_stderr = subprocess.PIPE
        try:
            _log.debug('Running: %s', ' '.join(shlex.quote(arg) for arg in argv))
            proc = subprocess.run(
                argv,
                shell=False,
                encoding='utf-8',
                stdout=fh_stdout,
                stderr=fh_stderr,
                stdin=subprocess.PIPE,
            )
        except OSError:
            raise errors.DependencyError(f'Missing dependency: {os.path.basename(argv[0])}')
        else:
            stdout, stderr = proc.stdout, proc.stderr
            if cache:
                _command_output_cache[argv] = (stdout, stderr)
    if stderr and not ignore_errors:
        raise errors.ProcessError(stderr)
    return stdout
