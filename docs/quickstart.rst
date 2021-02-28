Quickstart
==========

This is a very concise overview of how to get ``upsies`` up and running.

Read the :doc:`installation manual <./installation>` for more details.

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

   $ upsies submit -h
   $ upsies submit <tracker> -h
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
