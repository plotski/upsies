from unittest.mock import Mock, call

from upsies.utils import cache


def test_cached_property():
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
