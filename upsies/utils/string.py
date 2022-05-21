"""
String formatting and parsing
"""

import importlib
import inspect
import re
import sys

import logging  # isort:skip
_log = logging.getLogger(__name__)


def group(name):
    """
    Return character group, e.g. "digits"

    This function simply returns an attribute from the built-in :mod:`string`
    module.

    :raise ValueError: if the built-in :mod:`string` module doesn't have
        attribute `name`
    """
    string_module = importlib.import_module('string')
    try:
        return getattr(string_module, name)
    except AttributeError:
        raise ValueError(f'No such character group: {name!r}')


def autodecode(bytes):
    """
    Decode `bytes` with autodetected encoding

    :raise ValueError: if autodetection fails

    :return: Decoded string
    :rtype: str
    """
    import chardet
    info = chardet.detect(bytes)
    encoding = info.get('encoding', None)
    if encoding:
        _log.debug('Decoding %r with %r', bytes[:100], encoding)
        return str(bytes, encoding)
    else:
        raise ValueError(f'Unable to autodetect encoding: {bytes!r}')


_capitalize_regex = re.compile(r'(\s*)(\S+)(\s*)')

def capitalize(text):
    """
    Capitalize each word in `text`

    Unlike :meth:`str.title`, only words at in front of a space or at the
    beginning of `text` are capitalized.
    """
    return ''.join(
        match.group(1) + match.group(2).capitalize() + match.group(3)
        for match in re.finditer(_capitalize_regex, text)
    )


def star_rating(rating, max_rating=10):
    """
    Return star rating string with the characters "★" (U+2605), "⯪" (U+2BEA) and
    "☆" (U+2605)

    :param float,int rating: Number between 0 and `max_rating`
    :param float,int max_rating: Maximum rating
    """
    import math
    rating = min(max_rating, max(0, rating))
    left = '\u2605' * math.floor(rating)
    if rating >= max_rating:
        middle = ''
    # Avoid floating point precision issues by rounding to 1 digit after comma
    elif round(rating % 1, 1) <= 0.3:
        middle = '\u2606'  # Empty star
    elif round(rating % 1, 1) < 0.7:
        middle = '\u2bea'  # Half star
    else:
        middle = '\u2605'  # Full star
    right = '\u2606' * (math.ceil(max_rating - rating) - 1)
    return f'{left}{middle}{right}'


if sys.version_info >= (3, 9, 0):
    def remove_prefix(string, prefix):
        return string.removeprefix(prefix)

    def remove_suffix(string, suffix):
        return string.removesuffix(suffix)

else:
    def remove_prefix(string, prefix):
        if string.startswith(prefix):
            return string[len(prefix):]
        else:
            return string

    def remove_suffix(string, suffix):
        if string.endswith(suffix):
            return string[:-len(suffix)]
        else:
            return string


def evaluate_fstring(template):
    """
    Deferred f-string evaluation

    Example:

    >>> template = 'Evaluate this: {sum((1, 2, 3)) * 2}'
    >>> evaluate_fstring(template)
    12

    References:

        https://pypi.org/project/f-yeah/
        https://stackoverflow.com/a/42497694
    """
    parent_frame = inspect.stack()[1].frame
    fstring = 'f' + repr(template)
    return eval(fstring, parent_frame.f_globals, parent_frame.f_locals)
