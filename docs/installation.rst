Installation
============

OS Support
----------

Any Linux or Unix distribution that provides the dependencies below should work.

Feel free to try other operating systems and report any issues_ you find.

.. _issues: https://github.com/plotski/upsies/issues

Dependencies
------------

* `Python <https://www.python.org/>`_ 3.6 or higher
* `mediainfo <https://mediaarea.net/en/MediaInfo>`_
* `ffmpeg <https://ffmpeg.org/>`_ (optional; only for creating screenshots)

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

      $ pipx upgrade upsies

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

Installing Latest Commit
------------------------

If you just want to run the current development version without having to clone,
you can also do that with `pipx`_.

For ``pipx --version >= 0.15.0.0``
    .. code:: sh

       $ pipx install 'git+https://github.com/plotski/upsies'

For ``pipx --version < 0.15.0.0``
    .. code:: sh

       $ pipx install upsies --spec 'git+https://github.com/plotski/upsies.git#egg=upsies'
