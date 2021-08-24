"""
String formatting and parsing
"""

import sys

import logging  # isort:skip
_log = logging.getLogger(__name__)


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


def star_rating(rating, max_rating=10):
    '''Return star rating string with the characters "★", "⯪" and "☆"'''
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
