"""
HTML parsing
"""

from .. import errors
from . import LazyModule

bs4 = LazyModule(module='bs4', namespace=globals())


def parse(string):
    """
    Return :class:`~.bs4.BeautifulSoup` instance

    :param string: HTML document

    :raise ContentError: if `string` is invalid HTML
    """
    try:
        return bs4.BeautifulSoup(str(string), features='html.parser')
    except Exception as e:
        raise errors.ContentError(f'Invalid HTML: {e}')


def dump(html, filepath):
    """
    Write `html` to `filepath` for debugging

    :param html: String or :class:`~.bs4.BeautifulSoup` instance
    """
    with open(filepath, 'w') as f:
        if isinstance(html, bs4.BeautifulSoup):
            f.write(html.prettify())
        else:
            f.write(parse(str(html)).prettify())
