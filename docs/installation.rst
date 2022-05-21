Installation
============

OS Support
----------

Any Linux or Unix distribution that provides the dependencies below should work.

For Windows, the instructions below reportedly work in WSL_.

Feel free to report any issues_ you find with your OS.

.. _issues: https://github.com/plotski/upsies/issues
.. _WSL: https://en.wikipedia.org/wiki/Windows_Subsystem_for_Linux

Dependencies
------------

* `Python <https://www.python.org/>`_ 3.6 or higher
* `mediainfo <https://mediaarea.net/en/MediaInfo>`_
* `ffmpeg <https://ffmpeg.org/>`_ (optional: screenshot creation)
* `ffprobe <https://ffmpeg.org/>`_ (optional: faster video duration detection)

Installing Current Release
--------------------------

:ref:`pipx <installing/pipx>` is the recommended installation tool. It creates a
separate virtual environment for each installed Python package that contains all
the dependencies to avoid conflicts and to make it trivial to uninstall packges
completely.

.. _pipx: https://pipxproject.github.io/pipx/
.. _installing/pipx:

pipx (recommended)
^^^^^^^^^^^^^^^^^^

1. Try installing `pipx`_ with your package manager, e.g.

   .. code-block:: sh

      $ sudo apt install pipx

   If that fails, this command should install ``pipx`` in ``~/.local``:

   .. code-block:: sh

      $ pip install --user pipx

2. Make sure ``~/.local/bin`` is in your ``PATH``. If you don't know how to do
   that, try this command:

   .. code-block:: sh

      $ python3 -m pipx ensurepath

3. Install ``upsies`` with ``pipx``:

   .. code-block:: sh

      $ pipx install upsies

4. Upgrade to the latest release:

   .. code-block:: sh

      $ pipx upgrade upsies --include-injected

5. Uninstall ``upsies``:

   .. code-block:: sh

      $ pipx uninstall upsies

pip
^^^

Installing with ``pip`` is messy because it installs everything in the same
environment and it doesn't provide any way to remove dependencies.

Only do this if you don't care or if :ref:`installing with pipx
<installing/pipx>` is not possible for some reason.

.. code-block:: sh

   $ # Install upsies
   $ pip install --user upsies
   $ # Update to the latest version
   $ pip install --user --upgrade upsies
   $ # Remove upsies (but not its dependencies)
   $ pip uninstall upsies

Installing from Git Repository
------------------------------

If you just want to run the current development version without having to clone,
you can also do that with `pipx`_.

For ``pipx --version >= 0.15.0.0``
    .. code:: sh

       $ # Initial installation
       $ pipx install 'git+git://github.com/plotski/upsies.git'
       $ # Upgrade existing installation to current commit
       $ pipx install 'git+git://github.com/plotski/upsies.git' --force
       $ # Install specific commit
       $ pipx install 'git+git://github.com/plotski/upsies.git@<COMMIT HASH>' --force

For ``pipx --version < 0.15.0.0``
    .. code:: sh

       $ # Initial installation
       $ pipx install upsies --spec 'git+git://github.com/plotski/upsies.git#egg=upsies'
       $ # Upgrade existing installation to current commit
       $ pipx install upsies --spec 'git+git://github.com/plotski/upsies.git#egg=upsies' --force
       $ # Install specific commit
       $ pipx install upsies --spec 'git+git://github.com/plotski/upsies.git@<COMMIT HASH>#egg=upsies' --force

Installing Specific Version
---------------------------

You can install an older version if the installed release has a bug.

.. code-block:: sh

   $ pipx install upsies==<version> --force

See https://pypi.org/project/upsies/#history for a list of versions.
