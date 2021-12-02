from unittest.mock import call

import pytest

from upsies.utils import iso


@pytest.mark.parametrize(
    argnames='country, exp_name',
    argvalues=(
        ('Peoples Republic of China', 'China'),
        ('asdf', 'asdf'),
        (('Iceland', 'tv', 'asdf', 'US'), ('Iceland', 'Tuvalu', 'asdf', 'United States')),
    ),
)
def test_country_name(country, exp_name):
    name = iso.country_name(country)
    assert name == exp_name

def test_country_name_caches_CountryConverter_instance(mocker):
    CountryConverter_mock = mocker.patch('country_converter.CountryConverter')
    iso._get_country_converter.cache_clear()
    try:
        for _ in range(3):
            iso.country_name('foo')
        assert CountryConverter_mock.call_args_list == [call()]
    finally:
        iso._get_country_converter.cache_clear()


@pytest.mark.parametrize(
    argnames='country, exp_code',
    argvalues=(
        ('Britain', 'GB'),
        ('asdf', 'asdf'),
        (('Iceland', 'tv', 'asdf', 'Britain', 'US'), ('IS', 'TV', 'asdf', 'GB', 'US')),
    ),
)
def test_country_code_2letter(country, exp_code):
    code = iso.country_code_2letter(country)
    assert code == exp_code

def test_country_code_2letter_caches_CountryConverter_instance(mocker):
    CountryConverter_mock = mocker.patch('country_converter.CountryConverter')
    iso._get_country_converter.cache_clear()
    try:
        for _ in range(3):
            iso.country_code_2letter('foo')
        assert CountryConverter_mock.call_args_list == [call()]
    finally:
        iso._get_country_converter.cache_clear()


@pytest.mark.parametrize(
    argnames='country, exp_tld',
    argvalues=(
        ('United Kingdom', 'uk'),
        ('asdf', 'asdf'),
        (('Iceland', 'tv', 'asdf', 'Britain', 'US'), ('is', 'tv', 'asdf', 'uk', 'us')),
    ),
)
def test_country_tld(country, exp_tld):
    tld = iso.country_tld(country)
    assert tld == exp_tld

def test_country_tld_caches_CountryConverter_instance(mocker):
    CountryConverter_mock = mocker.patch('country_converter.CountryConverter')
    iso._get_country_converter.cache_clear()
    try:
        for _ in range(3):
            iso.country_tld('foo')
        assert CountryConverter_mock.call_args_list == [call()]
    finally:
        iso._get_country_converter.cache_clear()
