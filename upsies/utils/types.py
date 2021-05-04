"""
CLI argument types

All types return normalized values and raise ValueError for invalid values.
"""

import enum
import re


class Bytes(int):
    """:class:`int` subclass that interprets units and unit prefixes"""

    _regex = re.compile(r'^(\d+(?:\.\d+|)) ?([a-zA-Z]{,3})$')
    _multipliers = {
        '': 1,
        'k': 1000,
        'M': 1000**2,
        'G': 1000**3,
        'T': 1000**4,
        'P': 1000**5,
        'Ki': 1024,
        'Mi': 1024**2,
        'Gi': 1024**3,
        'Ti': 1024**4,
        'Pi': 1024**5,
    }

    @classmethod
    def from_string(cls, string):
        match = cls._regex.search(string)
        if not match:
            raise ValueError(f'Invalid size: {string}')
        else:
            number = match.group(1)
            unit = match.group(2)
            if unit and unit[-1] == 'B':
                unit = unit[:-1]
            try:
                multiplier = cls._multipliers[unit]
            except KeyError:
                raise ValueError(f'Invalid unit: {unit}')
            else:
                return cls(int(float(number) * multiplier))

    def __new__(cls, value):
        if isinstance(value, str):
            return cls.from_string(value)
        else:
            return super().__new__(cls, value)

    def __str__(self):
        decimal_multipliers = (
            (prefix, multiplier)
            for prefix, multiplier in reversed(tuple(self._multipliers.items()))
            if len(prefix) == 1
        )
        binary_multipliers = (
            (prefix, multiplier)
            for prefix, multiplier in reversed(tuple(self._multipliers.items()))
            if len(prefix) == 2
        )

        def get_string(multipliers):
            for prefix, multiplier in multipliers:
                if self >= multiplier:
                    return f'{self / multiplier:.2f}'.rstrip('0').rstrip('.') + f' {prefix}B'
            return f'{int(self)} B'

        def number_of_decimal_places(number):
            string = str(''.join(c for c in str(number) if c in '1234567890.'))
            if '.' in string:
                return len(string.split('.', maxsplit=1)[1])
            else:
                return 0

        decimal_string = get_string(decimal_multipliers)
        binary_string = get_string(binary_multipliers)
        sorted_strings = sorted((decimal_string, binary_string),
                                key=number_of_decimal_places)
        return sorted_strings[0]


class ReleaseType(enum.Enum):
    """
    Enum with the values ``movie``, ``season``, ``episode`` and
    ``unknown``

    ``series`` is an alias for ``season``.

    All values are truthy except for ``unknown``.
    """

    movie = 'movie'
    season = 'season'
    series = 'season'
    episode = 'episode'
    unknown = 'unknown'

    def __bool__(self):
        return self is not self.unknown

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f'{type(self).__name__}.{self.value}'


class SceneCheckResult(enum.Enum):
    """
    Enum with the values ``true``, ``false``, ``renamed``, ``altered`` and
    ``unknown``

    All values are falsy except for ``true``.
    """

    true = 'true'
    false = 'false'
    renamed = 'renamed'
    altered = 'altered'
    unknown = 'unknown'

    def __bool__(self):
        return self is self.true

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f'{type(self).__name__}.{self.value}'
