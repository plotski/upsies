"""
Open a URL in a web browser
"""

import functools

from . import LazyModule, get_aioloop

import logging  # isort:skip
_log = logging.getLogger(__name__)

webbrowser = LazyModule(module='webbrowser', namespace=globals())


def open(url):
    """Attempt to open URL in default web browser"""
    # Don't block while the browser is being started
    wrapper = functools.partial(webbrowser.open_new_tab, str(url))
    loop = get_aioloop()
    loop.run_in_executor(None, wrapper)
