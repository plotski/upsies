import sys
from unittest.mock import Mock, call

import pytest

from upsies.utils import cache


def test_cached_property_caches_return_value_of_decorated_function():
    calculation_mock = Mock()
    calculation_mock.return_value = 'expensive result'

    class Foo():
        @cache.property
        def bar(self):
            return calculation_mock()

    foo = Foo()
    for _ in range(5):
        assert foo.bar == 'expensive result'
        assert calculation_mock.call_args_list == [call()]
    foo.bar = 'asdf'
    assert foo.bar == 'asdf'

@pytest.mark.skipif(sys.version_info < (3, 8), reason='Needs cached_property from Python >= 3.8')
def test_cached_property_is_cached_property_subclass():
    class Foo():
        @cache.property
        def bar(self):
            pass

    from functools import cached_property
    assert isinstance(Foo.bar, cached_property)
