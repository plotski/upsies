from unittest.mock import Mock, PropertyMock

from upsies.trackers.base import TrackerBase


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def make_TestTracker(**kwargs):
    class TestTracker(TrackerBase):
        name = 'asdf'
        label = 'AsdF'
        TrackerJobs = PropertyMock()
        TrackerConfig = PropertyMock()
        login = AsyncMock()
        logout = AsyncMock()
        is_logged_in = PropertyMock()
        get_announce_url = AsyncMock()
        upload = AsyncMock()

    return TestTracker(**kwargs)


def test_options():
    options = {'username': 'foo', 'password': 'bar'}
    tracker = make_TestTracker(options=options)
    assert tracker.options is options


def test_argument_definitions():
    assert TrackerBase.argument_definitions == {}
