from upsies import utils


def test_pretty_bytes():
    assert utils.pretty_bytes(1023) == '1023 B'
    assert utils.pretty_bytes(1024) == '1.00 KiB'
    assert utils.pretty_bytes(1024 + 1024 / 2) == '1.50 KiB'
    assert utils.pretty_bytes((1024**2) - 102.4) == '1023.90 KiB'
    assert utils.pretty_bytes(1024**2) == '1.00 MiB'
    assert utils.pretty_bytes((1024**3) * 123) == '123.00 GiB'
    assert utils.pretty_bytes((1024**4) * 456) == '456.00 TiB'
    assert utils.pretty_bytes((1024**5) * 456) == '456.00 PiB'


def test_closest_number():
    numbers = (10, 20, 30)
    for n in (-10, 0, 9, 10, 11, 14):
        assert utils.closest_number(n, numbers) == 10
    for n in (16, 19, 20, 21, 24):
        assert utils.closest_number(n, numbers) == 20
    for n in range(26, 50):
        assert utils.closest_number(n, numbers) == 30


def test_CaseInsensitiveString_equality():
    assert utils.CaseInsensitiveString('Foo') == 'foo'
    assert utils.CaseInsensitiveString('fOo') == 'FOO'
    assert utils.CaseInsensitiveString('foO') == 'foo'
    assert utils.CaseInsensitiveString('foo') != 'fooo'

def test_CaseInsensitiveString_identity():
    assert utils.CaseInsensitiveString('Foo') in ('foo', 'bar', 'baz')
    assert utils.CaseInsensitiveString('fOo') in ('FOO', 'BAR', 'BAZ')
    assert utils.CaseInsensitiveString('foO') not in ('fooo', 'bar', 'baz')

def test_CaseInsensitiveString_lt():
    assert utils.CaseInsensitiveString('foo') < 'Fooo'

def test_CaseInsensitiveString_le():
    assert utils.CaseInsensitiveString('foo') <= 'Foo'

def test_CaseInsensitiveString_gt():
    assert utils.CaseInsensitiveString('Fooo') > 'foo'

def test_CaseInsensitiveString_ge():
    assert utils.CaseInsensitiveString('Foo') >= 'foo'


def test_is_sequence():
    assert utils.is_sequence((1, 2, 3))
    assert utils.is_sequence([1, 2, 3])
    assert not utils.is_sequence('123')
