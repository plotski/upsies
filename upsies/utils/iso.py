"""
Translation between country names and various codes
"""

import functools
import logging


@functools.lru_cache(maxsize=None)
def _get_country_converter():
    import country_converter
    country_converter_logger = logging.getLogger('country_converter')
    country_converter_logger.setLevel(logging.CRITICAL)
    return country_converter.CountryConverter()


def _flatten_sequence(seq):
    return tuple(
        item
        for subseq in seq
        for item in subseq
    )


def _convert(countries, to):
    values = _flatten_sequence(
        _get_country_converter().convert(
            countries,
            to=to,
            enforce_list=True,
            not_found=None,  # Return original input
        )
    )
    if isinstance(countries, str) and len(values) == 1:
        return values[0]
    else:
        return tuple(values)


def country_name(country):
    """
    Convert vague country name to consistent name

    :param country: Country name or code, e.g. "Russian Federation" (official
        name), "USA" (common abbreviation), "Korea" (short name), "fr"
        (2-character country code), etc.
    :type country: str or sequence

    :return: Country name or :class:`tuple` of country names, depending on
        `country` argument
    """
    return _convert(country, 'name_short')


def country_code_2letter(country):
    """
    Convert vague country names to ISO 3166-1 alpha-2 codes

    :param country: Country name or code, e.g. "Russian Federation" (official
        name), "USA" (common abbreviation), "Korea" (short name), "fr"
        (2-character country code), etc.
    :type country: str or sequence

    :return: Country code or :class:`tuple` of country codes, depending on
        `country` argument
    """
    return _convert(country, 'ISO2')


def country_tld(country):
    """
    Convert vague country names to top level domains

    This function behaves exactly like :func:`country_codes_2letter` except
    that:

        * Values are lower case.
        * For the United Kingdom, the value is "uk", not "gb".
    """
    def convert(tld):
        return ('uk' if tld == 'GB' else tld).lower()

    tlds = _convert(country, 'ISO2')
    if isinstance(tlds, str):
        return convert(tlds)
    else:
        return tuple(convert(tld) for tld in tlds)
