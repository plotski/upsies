Developer Reference
===================

Design
------

``upsies`` uses multiple abstraction layers for better maintability and
extensibility. This also makes it possible to use ``upsies`` as a toolkit for
your own Python projects.

In general, functions and classes take everything they need as arguments to make
them more predictable and easier to replace if necessary.

Utilities
^^^^^^^^^

:mod:`Utilities <upsies.utils>` are the lowest abstraction layer. They do the most
basic work like performing HTTP requests and executing subprocesses.

Utilities also provide high-level tools for creating torrents and screenshots,
querying online databases, etc. They produce convenient objects and exceptions
that are fit for presentation to the user.

Jobs
^^^^

:mod:`Jobs <upsies.jobs>` are the intermediaries between utilities and a user
interface. They provide data from utilities to the UI and handle user input.

Jobs are instantiated with all the necessary input, e.g. from CLI arguments or
configuration files.

For example, :class:`~.jobs.screenshots.ScreenshotsJob` takes the video file,
the desired number of screenshots and a list of specific screenshot
timestamps. It uses :mod:`.utils.timestamp` and :mod:`.utils.video` to validate
the specific timestamps, add more timestamps until the desired number of
screenshots is reached and then runs :func:`.utils.screenshot.create`. The
resulting screenshot paths are then made available via
:class:`~.utils.signal.Signal`\ s which the UI can connect to.

It's also possible to connect one job's output to another job's input. For
example, :attr:`~.ScreenshotsJob.output` can be connected to
:class:`~.ImageHostJob.upload` to upload screenshots as they are created.

Commands
^^^^^^^^

Commands are specific to the TUI. They represent CLI subcommands and have only
two very simple purposes:

#. Specify one or more jobs to execute.

#. Translate CLI arguments and configuration file contents into arguments for
   those jobs.

Trackers
^^^^^^^^

:mod:`Trackers <upsies.trackers>` implement anything that is specific to a
certain tracker. They provide a list of jobs that generate the necessary
metadata as well as an upload method to upload that metadata.

Index
-----

.. autosummary::
   :toctree:
   :template: autosummary-template.rst
   :nosignatures:
   :recursive:

   upsies.utils
   upsies.jobs
   upsies.trackers
   upsies.errors
