"""
CLI argument types

All types return normalized values and raise ValueError for invalid values.
"""

import enum
import re


def Integer(value, min=None, max=None):
    """
    Return :class:`int` subclass with minimum and maximum value

    >>> i = Integer(5, min=0, max=10)
    >>> type(i)(100)
    >>> ValueError: Maximum is 10
    """
    # There's a Python bug that prevents us from overloading min() and max()
    # with variables in the "class ...:" namespace
    min_ = min
    max_ = max

    class Integer(int):
        min = min_
        """Minimum value"""

        max = max_
        """Maximum value"""

        def __new__(cls, value):
            try:
                i = int(float(value))
            except (ValueError, TypeError):
                raise ValueError(f'Invalid integer value: {value!r}')

            if cls.min is not None and i < cls.min:
                raise ValueError(f'Minimum is {cls.min}')
            elif cls.max is not None and i > cls.max:
                raise ValueError(f'Maximum is {cls.max}')
            else:
                return super().__new__(cls, i)

        def __str__(self):
            return str(int(self))

        def __repr__(self):
            string = f'{type(self).__name__}({super().__repr__()}'
            if min is not None:
                string += f', min={min!r}'
            if max is not None:
                string += f', max={max!r}'
            string += ')'
            return string

    return Integer(value)


def Choice(value, options, empty_ok=False):
    """
    Return :class:`str` subclass that can only have instances that are equal to
    an item of `options`

    :param value: Initial value
    :param options: Iterable of allowed instances
    :param bool empty_ok: Whether an emptry string is valid even if it is not in
        of `options`

    :raise ValueError: if instantiation is attempted with a value that is not in
        `options`
    """
    options_str = tuple(sorted(str(o) for o in options))

    class Choice(str):
        options = options_str

        def __new__(cls, val):
            val_str = str(val)
            if val_str not in cls.options and (val_str or not empty_ok):
                raise ValueError(f'Not one of {", ".join(cls.options)}: {val}')
            else:
                return super().__new__(cls, val)

        def __str__(self):
            return super().__str__()

        def __repr__(self):
            return f'{type(self).__name__}({super().__repr__()}, options={self.options!r})'

    return Choice(value)


class Bool(str):
    """
    :class:`str` subclass with boolean value

    Truthy strings: ``true``, ``yes``, ``on``, ``1``
    Falsy strings: ``false``, ``no``, ``off``, ``0``
    """

    _truthy = re.compile(r'^(?:true|yes|on|1|yup|yay)$', flags=re.IGNORECASE)
    _falsy = re.compile(r'^(?:false|no|off|0|nope|nay|nah)$', flags=re.IGNORECASE)

    def __new__(cls, value):
        self = super().__new__(cls, value)
        if cls._truthy.search(self):
            self._bool = True
        elif cls._falsy.search(self):
            self._bool = False
        else:
            raise ValueError(f'Invalid boolean value: {value!r}')
        return self

    def __bool__(self):
        return self._bool

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return other._bool == self._bool
        elif isinstance(other, bool):
            return other == self._bool
        else:
            return NotImplemented

    def __repr__(self):
        return f'{type(self).__name__}({super().__str__()!r})'


class Bytes(int):
    """:class:`int` subclass with binary or decimal unit prefix"""

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
        """Parse `string` like ``4kB`` or ``1.024 KiB``"""
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

    def format(self, prefix='shortest', decimal_places=2, trailing_zeros=False):
        """
        Return human-readable string

        :param str prefix: Unit prefix, must be one of ``binary`` (1000 -> "1
            kB"), ``decimal`` (1024 -> "1 KiB") or ``shortest`` (automatically
            pick the string representation with the fewest decimal places)
        :param int decimal_places: How many decimal places to include
        :param bool trailing_zeros: Whether to remove zeros on the right of the
            decimal places
        """
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

        string_format = f'{{number:.{decimal_places}f}}'

        def get_string(multipliers):
            for prefix, multiplier in multipliers:
                if self >= multiplier:
                    number = strip_trailing_zeros(string_format.format(number=self / multiplier))
                    return f'{number} {prefix}B'
            number = strip_trailing_zeros(string_format.format(number=int(self)))
            return f'{number} B'

        def strip_trailing_zeros(string):
            # Only strip zeros from decimal places (not from "100")
            if not trailing_zeros and '.' in string:
                return string.rstrip('0').rstrip('.') or '0'
            else:
                return string

        def number_of_decimal_places(string):
            number = str(''.join(c for c in str(string) if c in '1234567890.'))
            if '.' in number:
                return len(number.split('.', maxsplit=1)[1])
            else:
                return 0

        if prefix == 'binary':
            return get_string(binary_multipliers)
        elif prefix == 'decimal':
            return get_string(decimal_multipliers)
        elif prefix == 'shortest':
            decimal_string = get_string(decimal_multipliers)
            binary_string = get_string(binary_multipliers)
            sorted_strings = sorted((decimal_string, binary_string),
                                    key=number_of_decimal_places)
            return sorted_strings[0]
        else:
            raise ValueError(f'Invalid prefix: {prefix!r}')

    def __str__(self):
        return self.format()

    def __repr__(self):
        return f'{type(self).__name__}({int(self)!r})'


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
