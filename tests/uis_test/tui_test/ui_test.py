import asyncio
import random
from unittest.mock import Mock, call

import pytest
from prompt_toolkit.application import Application
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.output import DummyOutput

from upsies.uis.tui.ui import UI


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture(autouse='module')
def mock_app(mocker):
    app = Application(
        input=create_pipe_input(),
        output=DummyOutput(),
    )
    mocker.patch('upsies.uis.tui.ui.UI._make_app', Mock(return_value=app))
    mocker.patch('upsies.uis.tui.ui.UI._container', Mock(children=[]), create=True)
    mocker.patch('upsies.uis.tui.ui.UI._layout', Mock(), create=True)
    mocker.patch('upsies.uis.tui.ui.UI._initial_placeholder', Window(), create=True)

@pytest.fixture(autouse='module')
def mock_JobWidget(mocker):
    job_widget = Mock(
        __pt_container__=Mock(return_value=(Window())),
        is_interactive=random.choice((True, False)),
        job=Mock(wait=AsyncMock()),
    )
    mocker.patch('upsies.uis.tui.widgets.JobWidget', Mock(return_value=job_widget))

async def block():
    await asyncio.sleep(300)


def test_run_gets_exception_from_application(mocker):
    ui = UI(jobs=())
    mocker.patch.object(ui, '_do_jobs', block)
    mocker.patch.object(ui._app, 'run', Mock(side_effect=RuntimeError('This is bad')))
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run()

def test_run_gets_exception_from_do_jobs(mocker):
    ui = UI(jobs=())
    mocker.patch.object(ui, '_do_jobs', AsyncMock(side_effect=RuntimeError('This is bad')))
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run()

def test_run_gets_exception_from_JobWidget(mocker):
    mocker.patch('upsies.uis.tui.widgets.JobWidget', Mock(side_effect=RuntimeError('This is bad')))
    ui = UI(jobs=(Mock(),))
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run()

def test_run_gets_first_exception_from_job_start(mocker):
    ui = UI(jobs=(
        Mock(wait=block),
        Mock(wait=block),
        Mock(start=Mock(side_effect=RuntimeError('This is bad'))),
        Mock(start=Mock(side_effect=RuntimeError('This is also bad'))),
    ))
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run()

def test_run_gets_first_exception_from_job_wait(mocker):
    ui = UI(jobs=(
        Mock(wait=block),
        Mock(wait=block),
        Mock(wait=AsyncMock(side_effect=RuntimeError('This is bad'))),
        Mock(wait=AsyncMock(side_effect=RuntimeError('This is also bad'))),
    ))
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run()

def test_run_gets_first_unhandled_exception(mocker):
    async def raise_exception_in_task1():
        async def bad():
            raise RuntimeError('This is bad')
        asyncio.ensure_future(bad())

    async def raise_exception_in_task2():
        async def bad():
            raise RuntimeError('This is also bad')
        asyncio.ensure_future(bad())

    ui = UI(jobs=(
        Mock(wait=block),
        Mock(wait=block),
        Mock(wait=raise_exception_in_task1),
        Mock(wait=raise_exception_in_task2),
    ))
    asyncio.get_event_loop().call_later(1, ui._app.exit)  # Fail test after 1 second
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run()

def test_run_gets_returns_exit_code_from_final_job(mocker):
    ui = UI(jobs=(
        Mock(exit_code=1, wait=AsyncMock()),
        Mock(exit_code=2, wait=AsyncMock()),
        Mock(exit_code=3, wait=AsyncMock()),
    ))
    assert ui.run() == 3

def test_all_jobs_are_stopped_if_one_job_exits_with_exit_code_greater_zero(mocker):
    ui = UI(jobs=(
        Mock(exit_code=0, wait=block),
        Mock(exit_code=1, wait=AsyncMock()),
        Mock(exit_code=0, wait=block),
    ))
    assert ui.run() == 1

def test_jobs_with_autostart_set_to_False_are_not_started(mocker):
    jobs = [
        Mock(autostart=False, wait=AsyncMock()),
        Mock(autostart=True, wait=AsyncMock()),
        Mock(autostart=False, wait=AsyncMock()),
        Mock(autostart=True, wait=AsyncMock()),
    ]
    ui = UI(jobs=jobs)
    ui.run()
    for job in jobs:
        if job.autostart:
            assert job.start.call_args_list == [call()]
        else:
            assert job.start.call_args_list == []
