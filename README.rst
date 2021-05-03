``upsies`` is a toolkit for collecting, generating, normalizing and sharing
video metadata. It comes with a command line interface and can be used in shell
scripts. It is written in pure Python and is designed to be friendly to users
and useful for Python developers.

.. figure:: docs/demo.svg

   ``dummy`` is a no-op tracker and client. Every tracker defines a custom set
   of jobs that generate the metadata needed for submission.

Features
--------

* Search IMDb, TMDb and TVmaze for ID
* Generate standardized release name
* Create screenshots at hand-picked or auto-generated timestamps
* Upload screenshots to an image hosting service
* Create ``.torrent`` file and add it to supported BitTorrent client or copy it
  to a watch directory
* Identify scene releases and check if they were altered
* Submit metadata to a supported tracker
* Do everything simultaneously

``upsies`` is developed on `GitHub <https://github.com/plotski/upsies>`_.

The latest release is available on `PyPI <https://pypi.org/project/upsies>`_.

Documentation is hosted on `Read the Docs <https://upsies.readthedocs.io/en/latest/>`_.
