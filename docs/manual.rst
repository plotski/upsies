User Manual
===========

upsies comes with a mixed TUI/CLI interface. Subcommands provide a variety of
functions that can be configured with options and configuration files. Every
subcommand (and subsubcommand) provides a ``--help/-h`` option that explains
what it does and the arguments it accepts.

Input/Output
------------

Subcommands do one or more jobs and print the result to stdout. If a subcommand
does multiple jobs (e.g. creating and uploading screenshots), the final result
is the last job's output. If stdout is not a TTY (e.g. when it is redirected to
a file or a pipe), the TUI is printed to stderr. For example, you can run
``upsies screenshots file.mkv --upload-to imgbox | xclip`` and paste the result.

User input comes from configuration files, CLI arguments and interactive
prompts. You should only be bothered by a prompt if upsies is unsure about its
autodetection capabilities.

Configuration files
-------------------

Configuration is stored in INI files beneath ``$HOME/.config/upsies/`` or
``$XDG_CONFIG_HOME/upsies/`` if ``$XDG_CONFIG_HOME`` is set. You can edit
configuration options with a text editor or with ``upsies set <option>
<value>``.

.. warning:: You will lose comments and order if you use the ``set`` subcommand.
             It is recommended to edit the configuration files in a text editor.

``upsies set`` without any other arguments prints a list of configuration
options and their values. To get the value of a specific option, run ``upsies
set <option>``.

Along with some more information, ``upsies set -h`` prints a list of options
with their type.

Caching
-------

Generated metadata is cached and re-used as much as possible. You can cancel
upsies at any time, run the same command again, and it should pick up where it
stopped.

.. note:: The torrent can only be created in one go.

If you made a mistake and you need to regenerate metadata, use the
``--ignore-cache/-C`` option.

.. note:: ``--ignore-cache/-C`` is a global option and must come before any
          subcommand.

For easy inspection and debugging, cached metadata is stored in files beneath
``$HOME/.cache/upsies/`` or ``$XDG_CACHE_HOME/upsies/`` if ``$XDG_CACHE_HOME``
is set. You can also set ``config.main.cache_directory`` to permanently change
the location of cache files.

The size of all cache files combined is limited to 20 MB by default. The oldest
files are purged until the size limit is no longer exceeded. You can change the
cache size limit by setting ``config.main.max_cache_size``.
