from unittest.mock import Mock

import pytest

from upsies.utils.scene import base


@pytest.fixture
def testdb():
    class TestDb(base.SceneDbApiBase):
        name = 'scn'
        label = 'SCN'
        search = Mock()

    return TestDb()

def test_normalize_query(testdb):
    assert testdb._normalize_query(('foo  bar ', ' baz')) == ['foo', 'bar', 'baz']

def test_normalize_results(testdb):
    assert testdb._normalize_results(('Foo', 'bar', 'BAZ')) == ['bar', 'BAZ', 'Foo']
