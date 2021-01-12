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

For example, :class:`~.jobs.screenshots.ScreenshotsJob` takes a video file, the
desired number of screenshots and a list of specific timestamps. It uses
:mod:`.utils.timestamp` and :mod:`.utils.video` to validate the specific
timestamps and add more until the desired number of screenshots is reached and
then loops over :func:`.utils.screenshot.create`.

The resulting screenshot paths are published via a
:class:`~.utils.signal.Signal`. The UI uses that signal to display the paths of
created screenshots as they appear. Other jobs can also connect to it, e.g.
:class:`~.jobs.imghost.ImageHostJob` uploads screenshots as soon as they are
ready.

User Interface
^^^^^^^^^^^^^^

The UI manages jobs, which basically means starting them and then wait until
they are finished.

The UI also passes user input to jobs and displays output and errors from jobs.

For example, a :class:`subcommand <upsies.uis.tui.commands.CommandBase>` in the
default UI specifies a list of jobs and translates CLI arguments and
configuration file contents into arguments for those jobs.

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
   upsies.uis
   upsies.trackers
   upsies.errors
