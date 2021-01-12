Quickstart
==========

These commands should get you started quickly. Inexperienced users should read
the :doc:`installation manual <./installation>`.

Installation
------------

.. code-block:: sh

   $ sudo apt install pipx ffmpeg mediainfo
   $ pipx install upsies

Help
----

.. code-block:: sh

   $ upsies -h
   $ upsies <command> -h

Configuration
-------------

.. code-block:: sh

   $ upsies set # List options
   $ upsies set <option> <value>
   $ $EDITOR ~/.config/upsies/*.ini

Submission
----------

.. code-block:: sh

   $ upsies submit <tracker> <path/to/content> \
     [--add-to <client>] \
     [--copy-to <path/to/watch/directory>]

Upgrading
---------

.. code-block:: sh

   $ pipx upgrade upsies

Uninstalling
------------

.. code-block:: sh

   $ pipx uninstall upsies
