import asyncio
from unittest.mock import Mock, PropertyMock, call

import pytest

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


def test_config():
    config = {'username': 'foo', 'password': 'bar'}
    tracker = make_TestTracker(config=config)
    assert tracker.config is config


def test_cli_args():
    tracker = make_TestTracker(cli_args='mock args')
    assert tracker.cli_args == 'mock args'


def test_argument_definitions():
    assert TrackerBase.argument_definitions == {}


@pytest.mark.asyncio
async def test_with_login_calls_login(mocker):
    tracker = make_TestTracker()
    type(tracker).is_logged_in = PropertyMock(return_value=False)
    await tracker.with_login(AsyncMock()())
    assert tracker.login.call_args_list == [call()]

@pytest.mark.asyncio
async def test_with_login_does_not_call_login(mocker):
    tracker = make_TestTracker()
    type(tracker).is_logged_in = PropertyMock(return_value=True)
    await tracker.with_login(AsyncMock()())
    assert tracker.login.call_args_list == []

@pytest.mark.asyncio
async def test_with_login_calls_logout(mocker):
    tracker = make_TestTracker()
    await tracker.with_login(AsyncMock()(), logout=True)
    assert tracker.logout.call_args_list == [call()]

@pytest.mark.asyncio
async def test_with_login_does_not_call_logout(mocker):
    tracker = make_TestTracker()
    await tracker.with_login(AsyncMock()(), logout=False)
    assert tracker.logout.call_args_list == []

@pytest.mark.asyncio
async def test_with_login_calls_coros(mocker):
    coros = (
        asyncio.ensure_future(AsyncMock()()),
        asyncio.ensure_future(AsyncMock()()),
        asyncio.ensure_future(AsyncMock()()),
    )
    tracker = make_TestTracker()
    await tracker.with_login(*coros)
    for coro in coros:
        print(coro, dir(coro))
        assert coro.done()

@pytest.mark.asyncio
async def test_with_login_returns_return_value_from_last_coro(mocker):
    coros = (
        asyncio.ensure_future(AsyncMock(return_value=1)()),
        asyncio.ensure_future(AsyncMock(return_value=2)()),
        asyncio.ensure_future(AsyncMock(return_value=3)()),
    )
    tracker = make_TestTracker()
    assert await tracker.with_login(*coros) == 3
