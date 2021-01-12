upsies
======

``upsies`` is a toolkit for collecting, generating, normalizing and sharing
metadata. It comes with a command line interface and can be used in shell
scripts. It is written in pure Python (ignoring CLI tools like ``ffmpeg`` and
``mediainfo``) and is designed to be friendly to normal users and useful for
Python developers.

..
   ``upsies`` is developed on `GitHub <https://github.com/plotski/upsies>`_. The
   latest release is available on `PyPI
   <https://pypi.org/project/upsies>`_. Documentation is hosted on `Read the Docs
   <https://upsies.readthedocs.io/en/latest/>`_.

Features
--------

* Search IMDb, TMDb and TVmaze for ID
* Generate standardized release name
* Create screenshots at hand-picked or auto-generated timestamps
* Upload screenshots to an image hosting service
* Create ``.torrent`` file and add it to supported BitTorrent client
* Add the ``.torrent`` file to a supported client or copy it to a watch
  directory
* Submit metadata to supported private trackers
* Do all of this simultaneously

Supported Trackers
^^^^^^^^^^^^^^^^^^

* NBL

Supported BitTorrent Clients
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Transmission (only the daemon)

Supported Image Hosting Services
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* imgbox.com

Supported Database Services
^^^^^^^^^^^^^^^^^^^^^^^^^^^

* IMDb
* TMDb
* TVmaze

Table of Contents
-----------------

.. toctree::
   :maxdepth: 1

   quickstart
   installation
   reference
