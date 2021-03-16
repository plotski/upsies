from upsies.utils import string


def test_pretty_bytes():
    assert string.pretty_bytes(1023) == '1023 B'
    assert string.pretty_bytes(1024) == '1.00 KiB'
    assert string.pretty_bytes(1024 + 1024 / 2) == '1.50 KiB'
    assert string.pretty_bytes((1024**2) - 102.4) == '1023.90 KiB'
    assert string.pretty_bytes(1024**2) == '1.00 MiB'
    assert string.pretty_bytes((1024**3) * 123) == '123.00 GiB'
    assert string.pretty_bytes((1024**4) * 456) == '456.00 TiB'
    assert string.pretty_bytes((1024**5) * 456) == '456.00 PiB'
