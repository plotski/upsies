import asyncio
import sys
from types import SimpleNamespace
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
    mocker.patch('upsies.uis.tui.ui.UI._jobs_container', Mock(children=[]), create=True)
    mocker.patch('upsies.uis.tui.ui.UI._layout', Mock(), create=True)

@pytest.fixture(autouse='module')
def mock_JobWidget(mocker):
    job_widget = Mock(
        __pt_container__=Mock(return_value=(Window())),
        is_interactive=None,
        job=Mock(wait=AsyncMock()),
    )
    mocker.patch('upsies.uis.tui.widgets.JobWidget', Mock(return_value=job_widget))


def test_add_jobs_registers_signals(mocker):
    jobs = (
        Mock(name='a', wait=AsyncMock(), exit_code=0),
        Mock(name='b', wait=AsyncMock(), exit_code=0),
        Mock(name='c', wait=AsyncMock(), exit_code=0),
        Mock(name='d', wait=AsyncMock(), exit_code=0),
    )
    job_widgets = (
        Mock(name='w.a', is_interactive=True, __pt_container__=Mock(return_value=(Window()))),
        Mock(name='w.b', is_interactive=False, __pt_container__=Mock(return_value=(Window()))),
        Mock(name='w.c', is_interactive=True, __pt_container__=Mock(return_value=(Window()))),
        Mock(name='w.d', is_interactive=False, __pt_container__=Mock(return_value=(Window()))),
    )
    JobWidget_mock = mocker.patch('upsies.uis.tui.widgets.JobWidget', Mock(side_effect=job_widgets))
    ui = UI()
    ui.run(jobs)
    assert JobWidget_mock.call_args_list == [
        call(jobs[0]),
        call(jobs[1]),
        call(jobs[2]),
        call(jobs[3]),
    ]
    for job, jobw in zip(jobs, job_widgets):
        if jobw.is_interactive:
            assert job.signal.register.call_args_list == [
                call('error', ui._exit),
                call('finished', ui._update_jobs_container),
            ]
        else:
            assert job.signal.register.call_args_list == [
                call('error', ui._exit),
            ]

def test_add_jobs_does_not_start_jobs_with_autostart_set_to_False():
    jobs = (
        Mock(autostart=False, wait=AsyncMock(), exit_code=0),
        Mock(autostart=True, wait=AsyncMock(), exit_code=0),
        Mock(autostart=False, wait=AsyncMock(), exit_code=0),
        Mock(autostart=True, wait=AsyncMock(), exit_code=0),
    )
    ui = UI()
    ui.run(jobs)
    for job in jobs:
        if job.autostart:
            assert job.start.call_args_list == [call()]
        else:
            assert job.start.call_args_list == []


def test_update_jobs_container_sorts_interactive_jobs_above_background_jobs():
    ui = UI()
    ui._jobs = {
        'a': SimpleNamespace(job=Mock(), widget=Mock(is_interactive=True), container=Mock()),
        'b': SimpleNamespace(job=Mock(), widget=Mock(is_interactive=False), container=Mock()),
        'c': SimpleNamespace(job=Mock(), widget=Mock(is_interactive=True), container=Mock()),
        'd': SimpleNamespace(job=Mock(), widget=Mock(is_interactive=False), container=Mock()),
    }
    ui._update_jobs_container()
    assert ui._jobs_container.children == [
        ui._jobs['a'].container,
        ui._jobs['c'].container,
        ui._jobs['b'].container,
        ui._jobs['d'].container,
    ]

def test_update_jobs_container_only_adds_first_unfinished_job():
    ui = UI()
    ui._jobs = {
        'a': SimpleNamespace(job=Mock(is_finished=False), widget=Mock(is_interactive=True), container=Mock()),
        'b': SimpleNamespace(job=Mock(is_finished=False), widget=Mock(is_interactive=False), container=Mock()),
        'c': SimpleNamespace(job=Mock(is_finished=False), widget=Mock(is_interactive=True), container=Mock()),
        'd': SimpleNamespace(job=Mock(is_finished=False), widget=Mock(is_interactive=False), container=Mock()),
        'e': SimpleNamespace(job=Mock(is_finished=False), widget=Mock(is_interactive=True), container=Mock()),
    }
    ui._layout = Mock()

    def assert_jobs_container(*keys, focused):
        jobs_container_id = id(ui._jobs_container)
        ui._update_jobs_container()
        assert id(ui._jobs_container) == jobs_container_id
        containers = [ui._jobs[k].container for k in keys]
        assert ui._jobs_container.children == containers
        assert ui._layout.focus.call_args_list[-1] == call(ui._jobs[focused].container)

    assert_jobs_container('a', 'b', 'd', focused='a')

    ui._jobs['a'].job.is_finished = True
    assert_jobs_container('a', 'c', 'b', 'd', focused='c')

    ui._jobs['b'].job.is_finished = True
    assert_jobs_container('a', 'c', 'b', 'd', focused='c')

    ui._jobs['d'].job.is_finished = True
    assert_jobs_container('a', 'c', 'b', 'd', focused='c')

    ui._jobs['c'].job.is_finished = True
    assert_jobs_container('a', 'c', 'e', 'b', 'd', focused='e')

    ui._jobs['e'].job.is_finished = True
    assert_jobs_container('a', 'c', 'e', 'b', 'd', focused='e')


def test_exception_is_raised_by_app(mocker):
    ui = UI()
    mocker.patch.object(ui._app, 'run', Mock(side_effect=RuntimeError('This is bad')))
    mocker.patch.object(ui, '_wait_for_all_jobs', AsyncMock())
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run(())

def test_exception_is_raised_by_wait_for_all_jobs(mocker):
    ui = UI()
    mocker.patch.object(ui, '_wait_for_all_jobs', AsyncMock(side_effect=RuntimeError('This is bad')))
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run(())

def test_exception_is_raised_by_background_coroutine():
    def delayed_exception():
        async def raise_exception():
            await asyncio.sleep(0.1)
            raise RuntimeError('This is bad')
        asyncio.ensure_future(raise_exception())

    jobs = (
        Mock(wait=AsyncMock(), start=delayed_exception, exit_code=0),
        Mock(wait=lambda: asyncio.sleep(100), exit_code=0),
        Mock(wait=AsyncMock(), exit_code=0),
    )
    ui = UI()
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run(jobs)
    assert jobs[0].wait.call_args_list == [call()]
    assert jobs[2].wait.call_args_list == [call()]
    for job in jobs:
        assert job.finish.call_args_list == [call()]

def test_exceptions_are_raised_by_job_start():
    jobs = (
        Mock(wait=AsyncMock()),
        Mock(wait=AsyncMock()),
        Mock(wait=AsyncMock(), start=Mock(side_effect=RuntimeError('This is bad'))),
        Mock(wait=AsyncMock(), start=Mock(side_effect=RuntimeError('This is also bad'))),
    )
    ui = UI()
    with pytest.raises(RuntimeError, match=r'^This is bad$'):
        ui.run(jobs)
    for job in jobs:
        assert job.wait.call_args_list == []
        assert job.finish.call_args_list == []

def test_exceptions_are_raised_by_job_wait():
    jobs = (
        Mock(wait=AsyncMock(), exit_code=0),
        Mock(wait=AsyncMock(side_effect=RuntimeError('This is bad'))),
        Mock(wait=AsyncMock(), exit_code=0),
        Mock(wait=AsyncMock(side_effect=RuntimeError('This is also bad'))),
    )
    ui = UI()
    if sys.version_info >= (3, 7, 0):
        with pytest.raises(RuntimeError, match=r'^This is bad$'):
            ui.run(jobs)
    else:
        # In Python 3.6 asyncio.gather() raises exceptions randomly
        with pytest.raises(RuntimeError, match=r'^This is (?:also |)bad$'):
            ui.run(jobs)
    for job in jobs:
        assert job.wait.call_args_list == [call()]
        assert job.finish.call_args_list == [call()]

def test_jobs_return_with_nonzero_exit_code():
    jobs = (
        Mock(wait=AsyncMock(), exit_code=0),
        Mock(wait=AsyncMock(), exit_code=123),
        Mock(wait=AsyncMock(), exit_code=0),
        Mock(wait=AsyncMock(), exit_code=99),
    )
    ui = UI()
    assert ui.run(jobs) == 123
    for job in jobs:
        assert job.wait.call_args_list == [call()]
        assert job.finish.call_args_list == [call()]
