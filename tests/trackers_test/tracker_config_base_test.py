import pytest

from upsies.trackers.base import TrackerConfigBase


def test_no_config():
    class TestTrackerConfig(TrackerConfigBase):
        defaults = {
            'foo': '1',
            'bar': '',
            'baz': 'asdf',
        }
    assert TestTrackerConfig() == {
        'source': '',
        'exclude': [],
        'add-to': '',
        'copy-to': '',
        'foo': '1',
        'bar': '',
        'baz': 'asdf',
    }


def test_config_overloads_defaults():
    class TestTrackerConfig(TrackerConfigBase):
        defaults = {
            'foo': '1',
            'bar': '',
            'baz': 'asdf',
        }
    assert TestTrackerConfig({'bar': 'hello', 'foo': '2', 'source': '123'}) == {
        'source': '123',
        'exclude': [],
        'add-to': '',
        'copy-to': '',
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


def test_add_to_option():
    class TestTrackerConfig(TrackerConfigBase):
        defaults = {}

    with pytest.raises(ValueError, match=r'^Not one of [a-z, ]+: foo$'):
        TestTrackerConfig({'add-to': 'foo'})

    config = TestTrackerConfig()
    with pytest.raises(ValueError, match=r'^Not one of [a-z, ]+: foo$'):
        type(config['add-to'])('foo')


def test_argument_definitions():
    assert TrackerConfigBase.argument_definitions == {}
