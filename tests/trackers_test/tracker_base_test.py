from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies import trackers
from upsies.trackers.base import TrackerBase


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_trackers(mocker):
    existing_trackers = (Mock(), Mock(), Mock())
    submodules_mock = mocker.patch('upsies.utils.submodules')
    subclasses_mock = mocker.patch('upsies.utils.subclasses', return_value=existing_trackers)
    assert trackers.trackers() == existing_trackers
    assert submodules_mock.call_args_list == [call('upsies.trackers')]
    assert subclasses_mock.call_args_list == [call(trackers.base.TrackerBase, submodules_mock.return_value)]


def test_tracker_returns_TrackerBase_instance(mocker):
    existing_trackers = (Mock(), Mock(), Mock())
    existing_trackers[0].configure_mock(name='foo')
    existing_trackers[1].configure_mock(name='bar')
    existing_trackers[2].configure_mock(name='baz')
    mocker.patch('upsies.trackers.trackers', return_value=existing_trackers)
    assert trackers.tracker('bar', x=123) is existing_trackers[1].return_value
    assert existing_trackers[1].call_args_list == [call(x=123)]

def test_tracker_fails_to_find_class(mocker):
    existing_trackers = (Mock(), Mock(), Mock())
    existing_trackers[0].configure_mock(name='foo')
    existing_trackers[1].configure_mock(name='bar')
    existing_trackers[2].configure_mock(name='baz')
    mocker.patch('upsies.trackers.trackers', return_value=existing_trackers)
    with pytest.raises(ValueError, match='^Unsupported tracker: bam$'):
        trackers.tracker('bam', x=123)
    for t in existing_trackers:
        assert t.call_args_list == []


def make_TestTracker(**kwargs):
    class TestTracker(TrackerBase):
        name = 'asdf'
        label = 'AsdF'
        TrackerJobs = PropertyMock()
        TrackerConfig = PropertyMock()
        login = AsyncMock()
        logout = AsyncMock()
        upload = AsyncMock()

    return TestTracker(**kwargs)


def test_config():
    config = {'username': 'foo', 'password': 'bar'}
    tracker = make_TestTracker(config=config)
    assert tracker.config is config


def test_argument_definitions():
    assert TrackerBase.argument_definitions == {}
