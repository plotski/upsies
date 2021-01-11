import pytest

from upsies.trackers.base import TrackerConfigBase


def test_no_arguments():
    class TestTrackerConfig(TrackerConfigBase):
        defaults = {
            'foo': '1',
            'bar': '',
            'baz': 'asdf',
        }
    assert TestTrackerConfig(config={}) == {
        'announce': '',
        'source': '',
        'exclude': [],
        'foo': '1',
        'bar': '',
        'baz': 'asdf',
    }


def test_arguments_overload_defaults():
    class TestTrackerConfig(TrackerConfigBase):
        defaults = {
            'foo': '1',
            'bar': '',
            'baz': 'asdf',
        }
    assert TestTrackerConfig({'bar': 'hello', 'foo': '2', 'source': '123'}) == {
        'announce': '',
        'source': '123',
        'exclude': [],
        'foo': '2',
        'bar': 'hello',
        'baz': 'asdf',
    }


def test_arguments_that_are_not_in_defaults():
    class TestTrackerConfig(TrackerConfigBase):
        defaults = {
            'foo': '1',
            'bar': '',
            'baz': 'asdf',
        }
    with pytest.raises(TypeError, match=r"^Unknown option: 'bingo'$"):
        TestTrackerConfig({'bingo': 'bongo'})
