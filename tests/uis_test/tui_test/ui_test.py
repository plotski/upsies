import asyncio
import random
from unittest.mock import Mock

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

def test_run_gets_exception_from_job_start(mocker):
    ui = UI(jobs=(
        Mock(wait=block),
        Mock(wait=block),
        Mock(start=Mock(side_effect=RuntimeError('This is bad'))),
    ))
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run()

def test_run_gets_exception_from_job_wait(mocker):
    ui = UI(jobs=(
        Mock(wait=block),
        Mock(wait=block),
        Mock(wait=AsyncMock(side_effect=RuntimeError('This is bad'))),
    ))
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run()

def test_run_gets_unhandled_exception(mocker):
    async def ignore_exception():
        async def bad():
            raise RuntimeError('This is bad')
        asyncio.ensure_future(bad())

    ui = UI(jobs=(
        Mock(wait=block),
        Mock(wait=block),
        Mock(wait=ignore_exception),
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
