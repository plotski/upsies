import asyncio
import functools

from . import LazyModule

webbrowser = LazyModule(module='webbrowser', namespace=globals())

import logging  # isort:skip
_log = logging.getLogger(__name__)


def open(url):
    """Attempt to open URL in default web browser"""
    # Don't block while the browser is being started
    wrapper = functools.partial(webbrowser.open_new_tab, str(url))
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, wrapper)
