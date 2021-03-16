"""
String formatting and parsing
"""

import math


_byte_units = {
    'PiB': 1024 ** 5,
    'TiB': 1024 ** 4,
    'GiB': 1024 ** 3,
    'MiB': 1024 ** 2,
    'KiB': 1024,
}

def pretty_bytes(b):
    '''Return `b` as human-readable bytes, e.g. "24.3 MiB"'''
    for unit, bytes in _byte_units.items():
        if b >= bytes:
            return f'{b / bytes:.2f} {unit}'
    return f'{int(b)} B'
