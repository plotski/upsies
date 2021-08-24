import re

import pytest

from upsies.utils import string


@pytest.mark.parametrize(
    argnames='bytes, exp_string, exp_error',
    argvalues=(
        (b'\xf2\xd5\xd3\xd3\xcb\xc9\xca', 'Русский', None),  # Russian
        (b'\xf2\xe1\xf8\xe9\xfa', 'עברית', None),  # Hebrew
        (b'\xc5\xeb\xeb\xe7\xed\xe9\xea\xdc', 'Ελληνικά', None),  # Greek
        (b'\x1aE\xdf\xa3\xa3B\x86\x81\x01B', None, r"Unable to autodetect encoding: b'\x1aE\xdf\xa3\xa3B\x86\x81\x01B'"),
    ),
)
def test_autodecode(bytes, exp_string, exp_error):
    if exp_error:
        with pytest.raises(ValueError, match=rf'^{re.escape(exp_error)}$'):
            string.autodecode(bytes)
    else:
        assert string.autodecode(bytes) == exp_string


@pytest.mark.parametrize(
    argnames='ratings, exp_string',
    argvalues=(
        ((-0.0, -0.1, -10.5), '☆☆☆☆☆☆☆☆☆☆'),
        ((0, 0.1, 0.2, 0.3), '☆☆☆☆☆☆☆☆☆☆'), ((0.4, 0.5, 0.6), '⯪☆☆☆☆☆☆☆☆☆'), ((0.7, 0.8, 0.9), '★☆☆☆☆☆☆☆☆☆'),
        ((1, 1.1, 1.2, 1.3), '★☆☆☆☆☆☆☆☆☆'), ((1.4, 1.5, 1.6), '★⯪☆☆☆☆☆☆☆☆'), ((1.7, 1.8, 1.9), '★★☆☆☆☆☆☆☆☆'),
        ((2, 2.1, 2.2, 2.3), '★★☆☆☆☆☆☆☆☆'), ((2.4, 2.5, 2.6), '★★⯪☆☆☆☆☆☆☆'), ((2.7, 2.8, 2.9), '★★★☆☆☆☆☆☆☆'),
        ((3, 3.1, 3.2, 3.3), '★★★☆☆☆☆☆☆☆'), ((3.4, 3.5, 3.6), '★★★⯪☆☆☆☆☆☆'), ((3.7, 3.8, 3.9), '★★★★☆☆☆☆☆☆'),
        ((4, 4.1, 4.2, 4.3), '★★★★☆☆☆☆☆☆'), ((4.4, 4.5, 4.6), '★★★★⯪☆☆☆☆☆'), ((4.7, 4.8, 4.9), '★★★★★☆☆☆☆☆'),
        ((5, 5.1, 5.2, 5.3), '★★★★★☆☆☆☆☆'), ((5.4, 5.5, 5.6), '★★★★★⯪☆☆☆☆'), ((5.7, 5.8, 5.9), '★★★★★★☆☆☆☆'),
        ((6, 6.1, 6.2, 6.3), '★★★★★★☆☆☆☆'), ((6.4, 6.5, 6.6), '★★★★★★⯪☆☆☆'), ((6.7, 6.8, 6.9), '★★★★★★★☆☆☆'),
        ((7, 7.1, 7.2, 7.3), '★★★★★★★☆☆☆'), ((7.4, 7.5, 7.6), '★★★★★★★⯪☆☆'), ((7.7, 7.8, 7.9), '★★★★★★★★☆☆'),
        ((8, 8.1, 8.2, 8.3), '★★★★★★★★☆☆'), ((8.4, 8.5, 8.6), '★★★★★★★★⯪☆'), ((8.7, 8.8, 8.9), '★★★★★★★★★☆'),
        ((9, 9.1, 9.2, 9.3), '★★★★★★★★★☆'), ((9.4, 9.5, 9.6), '★★★★★★★★★⯪'), ((9.7, 9.8, 9.9), '★★★★★★★★★★'),
        ((10, 10.1, 10.5, 12), '★★★★★★★★★★'),
    ),
)
def test_star_rating(ratings, exp_string):
    for rating in ratings:
        assert string.star_rating(rating) == exp_string


def test_remove_prefix():
    assert string.remove_prefix('com.domain.www', 'com.') == 'domain.www'
    assert string.remove_prefix('com.domain.www', 'moc.') == 'com.domain.www'


def test_remove_suffix():
    assert string.remove_suffix('www.domain.com', '.com') == 'www.domain'
    assert string.remove_suffix('www.domain.com', '.moc') == 'www.domain.com'
