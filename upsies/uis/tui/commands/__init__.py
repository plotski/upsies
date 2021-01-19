"""
CLI subcommands

A command provides a :attr:`~.CommandBase.jobs` property that returns a sequence
of :class:`~.jobs.base.JobBase` instances.

It is important that the jobs are only instantiated once and the
:attr:`~.CommandBase.jobs` property doesn't create new jobs every time it is
accessed. The easiest way to achieve this is with the
:func:`~functools.cached_property` decorator.

CLI arguments are available as :attr:`~.CommandBase.args` and configuration
files as :attr:`~.CommandBase.config`. These should be used to create arguments
for jobs.

The docstrings of :class:`~.base.CommandBase` subclasses are used as the
description in the ``--help`` output.
"""

import functools

from ....utils import subclasses, submodules
from .base import CommandBase


@functools.lru_cache(maxsize=None)
def _register_commands():
    subcmdclss = sorted(subclasses(CommandBase, submodules(__package__)),
                        key=lambda subcmdcls: subcmdcls.names[0])
    for subcmdcls in subcmdclss:
        subcmdcls.register()


def run(args):
    """
    Instantiate :class:`~.base.CommandBase`

    This is just a thin wrapper around :meth:`~.base.CommandBase.run` that
    ensures all commands are registered first.

    :param args: CLI arguments
    """
    _register_commands()
    return CommandBase.run(args)
