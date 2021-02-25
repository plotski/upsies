from unittest.mock import Mock, call

import pytest

from upsies import trackers


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


def test_tracker_names(mocker):
    existing_trackers = (Mock(), Mock(), Mock())
    existing_trackers[0].configure_mock(name='FOO')
    existing_trackers[1].configure_mock(name='bar')
    existing_trackers[2].configure_mock(name='Baz')
    mocker.patch('upsies.trackers.trackers', return_value=existing_trackers)
    trackers.tracker_names() == ['bar', 'Baz', 'FOO']
