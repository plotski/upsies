import pytest

from upsies.trackers.base import TrackerConfigBase


def test_positional_arguments():
    class TestTrackerConfig(TrackerConfigBase):
        defaults = {
            'foo': '1',
            'bar': '',
            'baz': 'asdf',
        }
    with pytest.raises(TypeError, match=r'takes 1 positional argument but 2 were given'):
        TestTrackerConfig('hello')


def test_no_arguments():
    class TestTrackerConfig(TrackerConfigBase):
        defaults = {
            'foo': '1',
            'bar': '',
            'baz': 'asdf',
        }
    assert TestTrackerConfig() == {
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
    assert TestTrackerConfig(bar='hello', foo='2') == {
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
        TestTrackerConfig(bingo='bongo')
