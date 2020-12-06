upsies is a framework for automated metadata generation. It's comes with a
TUI/CLI interface but it can also be used in shell scripts or as a Python
library.

upsies is still in a pre-alpha state. There is no proper documenation yet, but
:code:`upsies --help` should get you started.

Installation
------------

.. code:: sh

   $ sudo apt install pipx

If :code:`pipx --version` is equal to or greater than 0.15.0.0:

.. code:: sh

   $ pipx install git+https://github.com/plotski/upsies

If :code:`pipx --version` is lower than 0.15.0.0:

.. code:: sh

   $ pipx install upsies --spec 'git+https://github.com/plotski/upsies.git#egg=upsies'

Setup
-----

.. code:: sh

   $ upsies -h
   $ upsies set -h
   $ upsies submit dummy path/to/files
