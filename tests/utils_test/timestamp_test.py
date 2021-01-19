import re

import pytest

from upsies.utils import timestamp


def test_pretty_timestamp_from_int():
    testcases = (
        (0, '0:00:00'),
        (1, '0:00:01'),
        (59, '0:00:59'),
        (60, '0:01:00'),
        (61, '0:01:01'),
        (60 * 60 - 1, '0:59:59'),
        (60 * 60, '1:00:00'),
        (10 * 60 * 60 + 1, '10:00:01'),
        (123 * 60 * 60 + 321, '123:05:21'),
    )
    for seconds, string in testcases:
        print(f'{seconds} seconds should be formatted as {string}')
        assert timestamp.pretty(seconds) == string


def test_pretty_timestamp_from_str():
    testcases = (
        ('0', '0:00:00'),
        ('1', '0:00:01'),
        ('123', '0:02:03'),
        ('1:2:3', '1:02:03'),
    )
    for instring, outstring in testcases:
        print(f'{instring} seconds should be formatted as {outstring}')
        assert timestamp.pretty(instring) == outstring


def test_pretty_timestamp_from_invalid_value():
    for value in ('-1', -1):
        with pytest.raises(ValueError, match=rf'^Timestamp must not be negative: {value}$'):
            timestamp.pretty(value)
    for value in ('hello',):
        with pytest.raises(ValueError, match=rf'^Invalid timestamp: {value!r}$'):
            timestamp.pretty(value)
    for value in ([1, 2, 3],):
        with pytest.raises(TypeError, match=rf'^Not a string or number: {re.escape(repr(value))}$'):
            timestamp.pretty(value)


def test_parse_timestamp_from_str():
    testcases = (
        ('0', 0),
        ('59', 59),
        ('60', 60),
        ('123.2', 123.2),
        ('1:00', 60),
        ('1:01', 61),
        ('1:02:03', 3600 + (2 * 60) + 3),
        ('1:02:03.456', 3600 + (2 * 60) + 3 + 0.456),
        ('1:2:3', 3600 + (2 * 60) + 3),
        ('123:04:55', (123 * 3600) + (4 * 60) + 55),
    )
    for string, seconds in testcases:
        print(f'{string} should be interpreted as {seconds} seconds')
        assert timestamp.parse(string) == seconds


def test_parse_timestamp_from_invalid_str():
    testcases = ('foo', '1:00f')
    for string in testcases:
        with pytest.raises(ValueError, match=rf'^Invalid timestamp: {string!r}$'):
            timestamp.parse(string)

    testcases = ('-1', '-100', '1:-2:3')
    for string in testcases:
        with pytest.raises(ValueError, match=rf'^Timestamp must not be negative: {string}$'):
            timestamp.parse(string)


def test_parse_timestamp_from_number():
    testcases = (0, 1, 1.5, 59, 60, 61, 300)
    for value in testcases:
        assert timestamp.parse(value) == value


def test_parse_timestamp_from_invalid_number():
    testcases = (-3, -59)
    for value in testcases:
        with pytest.raises(ValueError, match=rf'^Invalid timestamp: {value!r}$'):
            timestamp.parse(value)
