import pytest

from upsies.utils import timestamp


@pytest.mark.parametrize(
    argnames='seconds, string',
    argvalues=(
        (0, '0:00:00'),
        (1, '0:00:01'),
        (59, '0:00:59'),
        (60, '0:01:00'),
        (61, '0:01:01'),
        (60 * 60 - 1, '0:59:59'),
        (60 * 60, '1:00:00'),
        (10 * 60 * 60 + 1, '10:00:01'),
        (123 * 60 * 60 + 321, '123:05:21'),
    ),
    ids=lambda v: repr(v),
)
def test_pretty_timestamp_from_int(seconds, string):
    assert timestamp.pretty(seconds) == string


@pytest.mark.parametrize(
    argnames='instring, outstring',
    argvalues=(
        ('0', '0:00:00'),
        ('1', '0:00:01'),
        ('123', '0:02:03'),
        ('1:2:3', '1:02:03'),
    ),
    ids=lambda v: repr(v),
)
def test_pretty_timestamp_from_str(instring, outstring):
    assert timestamp.pretty(instring) == outstring

@pytest.mark.parametrize(
    argnames='value, exception, message',
    argvalues=(
        (-1, ValueError, r'^Timestamp must not be negative: -1$'),
        ('-1', ValueError, r'^Timestamp must not be negative: -1$'),
        ('hello', ValueError, r"^Invalid timestamp: 'hello'$"),
        ([1, 2, 3], TypeError, r"^Not a string or number: \[1, 2, 3\]$"),
    ),
    ids=lambda v: repr(v),
)
def test_pretty_timestamp_from_invalid_value(value, exception, message):
    with pytest.raises(exception, match=message):
        timestamp.pretty(value)


@pytest.mark.parametrize(
    argnames='string, seconds',
    argvalues=(
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
    ),
    ids=lambda v: repr(v),
)
def test_parse_timestamp_from_str(string, seconds):
    assert timestamp.parse(string) == seconds

@pytest.mark.parametrize(
    argnames='value, exception, message',
    argvalues=(
        ('foo', ValueError, r"^Invalid timestamp: 'foo'$"),
        ('1:00f', ValueError, r"^Invalid timestamp: '1:00f'$"),
        ('-1', ValueError, r'^Timestamp must not be negative: -1$'),
        ('-100', ValueError, r'^Timestamp must not be negative: -100$'),
        ('1:-2:3', ValueError, r'^Timestamp must not be negative: 1:-2:3$'),
    ),
    ids=lambda v: repr(v),
)
def test_parse_timestamp_from_invalid_str(value, exception, message):
    with pytest.raises(exception, match=message):
        timestamp.parse(value)


@pytest.mark.parametrize(
    argnames='value',
    argvalues=(0, 1, 1.5, 59, 60, 61, 300),
    ids=lambda v: repr(v),
)
def test_parse_timestamp_from_number(value):
    assert timestamp.parse(value) == value


@pytest.mark.parametrize(
    argnames='value, exception, message',
    argvalues=(
        (-3, ValueError, r'^Invalid timestamp: -3$'),
        (-61, ValueError, r'^Invalid timestamp: -61$'),
    ),
    ids=lambda v: repr(v),
)
def test_parse_timestamp_from_invalid_number(value, exception, message):
    with pytest.raises(exception, match=message):
        timestamp.parse(value)
