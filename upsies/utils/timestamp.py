"""
Timestamp parsing and normalizing
"""

def pretty(seconds):
    """
    Format `seconds` as "[[H+:]MM:]SS"

    Invalid values are returned unchanged.

    :param seconds: Number of seconds or hours, minutes and seconds as
        ":"-separated string
    :type seconds: int or float or "[[H+:]M+:]S+"

    :raise TypeError: if `seconds` is of invalid type
    :raise ValueError: if `seconds` is negative

    :return: "[[H+:]MM:]SS""
    """
    if isinstance(seconds, str):
        seconds = parse(seconds)

    if not isinstance(seconds, (int, float)):
        raise TypeError(f'Not a string or number: {seconds!r}')
    elif seconds < 0:
        raise ValueError(f'Timestamp must not be negative: {seconds!r}')

    return ':'.join((
        f'{int(seconds / 3600)}',
        f'{int(seconds % 3600 / 60):02d}',
        f'{int(seconds % 3600 % 60):02d}',
    ))


def parse(string):
    """
    Convert string format "[[H+:]MM:]SS" into integer

    :param string: Hours, minutes and seconds as ":"-separated string or number
        of seconds
    :type string: str or int or float

    :raise TypeError: if `string` is of invalid type
    :raise ValueError: if `string` has an invalid format

    :return: Number of seconds
    """
    if isinstance(string, (int, float)):
        if string >= 0:
            return string
        else:
            raise ValueError(f'Invalid timestamp: {string!r}')

    elif not isinstance(string, str):
        raise TypeError(f'Not a string or number: {string!r}')

    try:
        parts = [float(part) for part in string.split(':')]
    except ValueError:
        raise ValueError(f'Invalid timestamp: {string!r}')

    for part in parts:
        if part < 0:
            raise ValueError(f'Timestamp must not be negative: {string}')

    if len(parts) == 3:
        hours, mins, secs = parts
    elif len(parts) == 2:
        hours = 0
        mins, secs = parts
    elif len(parts) == 1:
        hours = mins = 0
        secs = parts[0]
    return (hours * 3600) + (mins * 60) + secs
