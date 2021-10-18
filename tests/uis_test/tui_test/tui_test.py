import asyncio
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, call, patch

import pytest
from prompt_toolkit.application import Application
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.output import DummyOutput

from upsies.uis.tui.tui import TUI


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
    mocker.patch('upsies.uis.tui.tui.TUI._make_app', Mock(return_value=app))
    mocker.patch('upsies.uis.tui.tui.TUI._jobs_container', Mock(children=[]), create=True)
    mocker.patch('upsies.uis.tui.tui.TUI._layout', Mock(), create=True)

@pytest.fixture(autouse='module')
def mock_JobWidget(mocker):
    job_widget = Mock(
        __pt_container__=Mock(return_value=(Window())),
        is_interactive=None,
        job=Mock(wait=AsyncMock()),
    )
    mocker.patch('upsies.uis.tui.jobwidgets.JobWidget', Mock(return_value=job_widget))


@pytest.mark.asyncio  # Ensure aioloop exists
async def test_add_jobs_does_not_add_same_job_twice(mocker):
    jobs = (Mock(), Mock(), Mock(), Mock())
    for job, name in zip(jobs, ('a', 'b', 'b', 'c')):
        job.configure_mock(name=name)
    mocker.patch('upsies.uis.tui.jobwidgets.JobWidget')
    mocker.patch('upsies.uis.tui.tui.to_container', Mock(return_value=True))
    ui = TUI()
    with pytest.raises(RuntimeError, match=r'^Job was already added: b$'):
        ui.add_jobs(*jobs)


@pytest.mark.asyncio  # Ensure aioloop exists
async def test_add_jobs_creates_JobWidgets(mocker):
    jobs = (Mock(), Mock(), Mock())
    JobWidget_mock = mocker.patch('upsies.uis.tui.jobwidgets.JobWidget')
    to_container_mock = mocker.patch('upsies.uis.tui.tui.to_container', Mock(return_value=True))
    ui = TUI()
    ui.add_jobs(*jobs)
    assert tuple(ui._jobs) == (jobs[0].name, jobs[1].name, jobs[2].name)
    for jobinfo in ui._jobs.values():
        assert jobinfo.widget == JobWidget_mock.return_value
        assert jobinfo.container == to_container_mock.return_value
    assert JobWidget_mock.call_args_list == [
        call(jobs[0], ui._app),
        call(jobs[1], ui._app),
        call(jobs[2], ui._app),
    ]
    assert to_container_mock.call_args_list == [
        call(JobWidget_mock.return_value),
        call(JobWidget_mock.return_value),
        call(JobWidget_mock.return_value),
    ]

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_add_jobs_registers_signals(mocker):
    jobs = (Mock(), Mock(), Mock())
    for job, name in zip(jobs, ('a', 'b', 'c')):
        job.configure_mock(name=name)
    job_widgets = (
        Mock(is_interactive=True, __pt_container__=Mock(return_value=(Window()))),
        Mock(is_interactive=False, __pt_container__=Mock(return_value=(Window()))),
        Mock(is_interactive=True, __pt_container__=Mock(return_value=(Window()))),
        Mock(is_interactive=False, __pt_container__=Mock(return_value=(Window()))),
    )
    mocker.patch('upsies.uis.tui.jobwidgets.JobWidget', Mock(side_effect=job_widgets))
    ui = TUI()
    ui.add_jobs(*jobs)
    for job, jobw in zip(jobs, job_widgets):
        if jobw.is_interactive:
            assert job.signal.register.call_args_list == [
                call('finished', ui._exit_if_all_jobs_finished),
                call('finished', ui._exit_if_job_failed),
                call('finished', ui._update_jobs_container),
            ]
        else:
            assert job.signal.register.call_args_list == [
                call('finished', ui._exit_if_all_jobs_finished),
                call('finished', ui._exit_if_job_failed),
            ]

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_add_jobs_calls_update_jobs_container(mocker):
    ui = TUI()
    mocker.patch.object(ui, '_update_jobs_container')
    ui.add_jobs()
    assert ui._update_jobs_container.call_args_list == [call()]


@pytest.mark.asyncio  # Ensure aioloop exists
async def test_update_jobs_container_autostarts_enabled_jobs():
    jobs = (
        (Mock(autostart=False, is_enabled=False, is_started=False), False),

        (Mock(autostart=False, is_enabled=False, is_started=True), False),
        (Mock(autostart=False, is_enabled=True, is_started=False), False),
        (Mock(autostart=True, is_enabled=False, is_started=False), False),

        (Mock(autostart=True, is_enabled=True, is_started=False), True),
        (Mock(autostart=True, is_enabled=False, is_started=True), False),
        (Mock(autostart=False, is_enabled=True, is_started=True), False),

        (Mock(autostart=True, is_enabled=True, is_started=True), False),
    )
    ui = TUI()
    ui.add_jobs(*(j[0] for j in jobs))
    for job, exp_start_called in jobs:
        if exp_start_called:
            assert job.start.call_args_list == [call()]
        else:
            assert job.start.call_args_list == []

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_update_jobs_container_sorts_interactive_jobs_above_background_jobs():
    ui = TUI()
    ui._jobs = {
        'a': SimpleNamespace(job=Mock(is_enabled=True), widget=Mock(is_interactive=True), container=Mock()),
        'b': SimpleNamespace(job=Mock(is_enabled=True), widget=Mock(is_interactive=False), container=Mock()),
        'c': SimpleNamespace(job=Mock(is_enabled=True), widget=Mock(is_interactive=True), container=Mock()),
        'd': SimpleNamespace(job=Mock(is_enabled=True), widget=Mock(is_interactive=False), container=Mock()),
        'e': SimpleNamespace(job=Mock(is_enabled=False), widget=Mock(is_interactive=True), container=Mock()),
        'f': SimpleNamespace(job=Mock(is_enabled=False), widget=Mock(is_interactive=False), container=Mock()),
    }
    ui._update_jobs_container()
    assert ui._jobs_container.children == [
        ui._jobs['a'].container,
        ui._jobs['c'].container,
        ui._jobs['b'].container,
        ui._jobs['d'].container,
    ]

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_update_jobs_container_only_adds_first_unfinished_job_and_focuses_it_if_no_job_has_errors():
    ui = TUI()
    ui._jobs = {
        'ai': SimpleNamespace(job=Mock(is_enabled=True, is_finished=False, errors=()), widget=Mock(is_interactive=True), container=Mock(name='aw')),
        'bn': SimpleNamespace(job=Mock(is_enabled=True, is_finished=False, errors=()), widget=Mock(is_interactive=False), container=Mock(name='bw')),
        'ci': SimpleNamespace(job=Mock(is_enabled=True, is_finished=False, errors=()), widget=Mock(is_interactive=True), container=Mock(name='cw')),
        'dn': SimpleNamespace(job=Mock(is_enabled=True, is_finished=False, errors=()), widget=Mock(is_interactive=False), container=Mock(name='dw')),
        'ei': SimpleNamespace(job=Mock(is_enabled=False, is_finished=False, errors=()), widget=Mock(is_interactive=True), container=Mock(name='ew')),
        'fn': SimpleNamespace(job=Mock(is_enabled=False, is_finished=False, errors=()), widget=Mock(is_interactive=False), container=Mock(name='fw')),
        'gi': SimpleNamespace(job=Mock(is_enabled=True, is_finished=False, errors=()), widget=Mock(is_interactive=True), container=Mock(name='gw')),
    }
    ui._layout = Mock()
    jobs_container_id = id(ui._jobs_container)

    def assert_jobs_container(*keys, focused):
        ui._update_jobs_container()
        assert id(ui._jobs_container) == jobs_container_id
        containers = [ui._jobs[k].container for k in keys]
        assert ui._jobs_container.children == containers
        assert ui._layout.focus.call_args_list[-1] == call(ui._jobs[focused].container)

    assert_jobs_container('ai', 'bn', 'dn', focused='ai')
    ui._jobs['ai'].job.is_finished = True
    assert_jobs_container('ai', 'ci', 'bn', 'dn', focused='ci')
    ui._jobs['bn'].job.is_finished = True
    assert_jobs_container('ai', 'ci', 'bn', 'dn', focused='ci')
    ui._jobs['dn'].job.is_finished = True
    assert_jobs_container('ai', 'ci', 'bn', 'dn', focused='ci')
    ui._jobs['ci'].job.is_finished = True
    assert_jobs_container('ai', 'ci', 'gi', 'bn', 'dn', focused='gi')

@pytest.mark.parametrize('failed_job_name', ('ai', 'bn', 'ci', 'dn', 'ei', 'fn', 'gi'))
@pytest.mark.asyncio  # Ensure aioloop exists
async def test_update_jobs_container_adds_all_jobs_it_if_one_job_has_errors(failed_job_name):
    ui = TUI()
    ui._jobs = {
        'ai': SimpleNamespace(job=Mock(is_enabled=True, is_finished=False, errors=()), widget=Mock(is_interactive=True), container=Mock(name='aw')),
        'bn': SimpleNamespace(job=Mock(is_enabled=True, is_finished=False, errors=()), widget=Mock(is_interactive=False), container=Mock(name='bw')),
        'ci': SimpleNamespace(job=Mock(is_enabled=True, is_finished=False, errors=()), widget=Mock(is_interactive=True), container=Mock(name='cw')),
        'dn': SimpleNamespace(job=Mock(is_enabled=True, is_finished=False, errors=()), widget=Mock(is_interactive=False), container=Mock(name='dw')),
        'ei': SimpleNamespace(job=Mock(is_enabled=False, is_finished=False, errors=()), widget=Mock(is_interactive=True), container=Mock(name='ew')),
        'fn': SimpleNamespace(job=Mock(is_enabled=False, is_finished=False, errors=()), widget=Mock(is_interactive=False), container=Mock(name='fw')),
        'gi': SimpleNamespace(job=Mock(is_enabled=True, is_finished=False, errors=()), widget=Mock(is_interactive=True), container=Mock(name='gw')),
    }
    ui._jobs[failed_job_name].job.errors = ('Some error message',)

    ui._layout = Mock()
    jobs_container_id = id(ui._jobs_container)

    def assert_jobs_container(*keys, focused):
        ui._update_jobs_container()
        assert id(ui._jobs_container) == jobs_container_id
        containers = [ui._jobs[k].container for k in keys]
        assert ui._jobs_container.children == containers

    assert_jobs_container('ai', 'ci', 'gi', 'bn', 'dn', focused='ai')


@pytest.mark.asyncio  # Ensure aioloop exists
async def test_run_calls_add_jobs(mocker):
    ui = TUI()
    mocker.patch.object(ui, 'add_jobs')
    mocker.patch.object(ui._app, 'run')
    ui.run(('a', 'b', 'c'))
    assert ui.add_jobs.call_args_list == [call('a', 'b', 'c')]

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_run_runs_application(mocker):
    ui = TUI()
    mocker.patch.object(ui, 'add_jobs')
    mocker.patch.object(ui._app, 'run')
    ui.run(('a', 'b', 'c'))
    assert ui._app.run.call_args_list == [call(set_exception_handler=False)]

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_run_raises_stored_exception(mocker):
    ui = TUI()
    mocker.patch.object(ui, 'add_jobs')
    mocker.patch.object(ui._app, 'run')
    mocker.patch.object(ui, '_get_exception', Mock(return_value=ValueError('foo')))
    with pytest.raises(ValueError, match=r'^foo$'):
        ui.run(('a', 'b', 'c'))

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_run_returns_first_nonzero_job_exit_code(mocker):
    ui = TUI()
    ui._jobs = {
        'a': SimpleNamespace(job=Mock(exit_code=0)),
        'b': SimpleNamespace(job=Mock(exit_code=1)),
        'c': SimpleNamespace(job=Mock(exit_code=2)),
        'd': SimpleNamespace(job=Mock(exit_code=3)),
    }
    mocker.patch.object(ui, 'add_jobs')
    mocker.patch.object(ui._app, 'run')
    mocker.patch.object(ui, '_get_exception', Mock(return_value=None))
    exit_code = ui.run(('a', 'b', 'c'))
    assert exit_code == 1

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_run_returns_zero_if_all_jobs_finished_successfully(mocker):
    ui = TUI()
    ui._jobs = {
        'a': SimpleNamespace(job=Mock(exit_code=0)),
        'b': SimpleNamespace(job=Mock(exit_code=0)),
        'c': SimpleNamespace(job=Mock(exit_code=0)),
        'd': SimpleNamespace(job=Mock(exit_code=0)),
    }
    mocker.patch.object(ui, 'add_jobs')
    mocker.patch.object(ui._app, 'run')
    mocker.patch.object(ui, '_get_exception', Mock(return_value=None))
    exit_code = ui.run(('a', 'b', 'c'))
    assert exit_code == 0


@pytest.mark.asyncio  # Ensure aioloop exists
async def test_exit_if_all_jobs_finished(mocker):
    ui = TUI()
    ui._jobs = {
        'a': SimpleNamespace(job=Mock(is_finished=False)),
        'b': SimpleNamespace(job=Mock(is_finished=False)),
        'c': SimpleNamespace(job=Mock(is_finished=False)),
        'd': SimpleNamespace(job=Mock(is_finished=False)),
    }
    mocker.patch.object(ui, '_exit')
    for job_name in ('a', 'b', 'c', 'd'):
        ui._exit_if_all_jobs_finished()
        assert ui._exit.call_args_list == []
        ui._exit_if_all_jobs_finished('mock job instance')
        assert ui._exit.call_args_list == []
        ui._jobs[job_name].job.is_finished = True
    ui._exit_if_all_jobs_finished()
    assert ui._exit.call_args_list == [call()]


@pytest.mark.asyncio  # Ensure aioloop exists
async def test_exit_if_job_failed_does_nothing_if_job_is_not_finished(mocker):
    ui = TUI()
    mocker.patch.object(ui, '_exit')
    ui._exit_if_job_failed(Mock(is_finished=False, exit_code=0, exceptions=()))
    assert ui._exit.call_args_list == []
    ui._exit_if_job_failed(Mock(is_finished=False, exit_code=123, exceptions=()))
    assert ui._exit.call_args_list == []

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_exit_if_job_failed_does_nothing_if_exit_code_is_zero(mocker):
    ui = TUI()
    mocker.patch.object(ui, '_exit')
    ui._exit_if_job_failed(Mock(is_finished=True, exit_code=0, exceptions=()))
    assert ui._exit.call_args_list == []

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_exit_if_job_failed_calls_exit_if_exit_code_is_nonzero(mocker):
    ui = TUI()
    mocker.patch.object(ui, '_exit')
    mocker.patch.object(ui, '_finish_jobs')
    ui._exit_if_job_failed(Mock(is_finished=True, exit_code=1, exceptions=()))
    assert ui._exit.call_args_list == [call()]


@pytest.mark.asyncio  # Ensure aioloop exists
async def test_exit_does_nothing_if_already_exited(mocker):
    ui = TUI()
    ui._app_terminated = True
    mocker.patch.object(ui, '_terminate_jobs', AsyncMock())
    ui._exit()
    assert ui._terminate_jobs.call_args_list == []
    assert ui._app_terminated is True

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_exit_waits_for_application_to_run(mocker, event_loop):
    ui = TUI()
    mocker.patch.object(ui, '_terminate_jobs', AsyncMock())
    mocker.patch.object(type(ui._app), 'is_running', PropertyMock(return_value=False))
    mocker.patch.object(type(ui._app), 'is_done', PropertyMock(return_value=False))
    # If asycnio.call_soon() is still mocked when the test is finished, pytest
    # just hangs. pytest.mark.asyncio seems to depend on it.
    with patch.object(event_loop, 'call_soon'):
        ui._exit()
        assert event_loop.call_soon.call_args_list == [call(ui._exit)]
    assert ui._terminate_jobs.call_args_list == []
    assert ui._app_terminated is False

@pytest.mark.asyncio
async def test_exit_calls_terminate_jobs(mocker):
    ui = TUI()
    mocker.patch.object(type(ui._app), 'is_running', PropertyMock(return_value=True))
    mocker.patch.object(type(ui._app), 'is_done', PropertyMock(return_value=False))
    mocker.patch.object(type(ui._app), 'exit', Mock())
    mocker.patch.object(ui, '_update_jobs_container', Mock())
    ui._exit()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert ui._app_terminated is True
    assert ui._app.exit.call_args_list == [call()]
    assert ui._update_jobs_container.call_args_list == [call()]

@pytest.mark.asyncio
async def test_exit_handles_exception_from_terminate_jobs(mocker):
    ui = TUI()
    mocker.patch.object(type(ui._app), 'is_running', PropertyMock(return_value=True))
    mocker.patch.object(type(ui._app), 'is_done', PropertyMock(return_value=False))
    mocker.patch.object(type(ui._app), 'exit', Mock())
    mocker.patch.object(ui, '_update_jobs_container', Mock())
    mocker.patch.object(ui, '_terminate_jobs', AsyncMock(side_effect=RuntimeError('foo!')))
    ui._exit()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert ui._app_terminated is True
    assert ui._app.exit.call_args_list == [call()]
    assert str(ui._exception) == 'foo!'
    assert isinstance(ui._exception, RuntimeError)
    assert ui._update_jobs_container.call_args_list == [call()]


@pytest.mark.parametrize('callback', (Mock(), None))
@pytest.mark.asyncio
async def test_terminate_jobs(callback, mocker):
    ui = TUI()
    ui._jobs = {
        'a': SimpleNamespace(job=Mock(is_started=False, is_finished=False, is_enabled=False, wait=AsyncMock())),
        'b': SimpleNamespace(job=Mock(is_started=False, is_finished=False, is_enabled=True, wait=AsyncMock())),
        'c': SimpleNamespace(job=Mock(is_started=False, is_finished=True, is_enabled=False, wait=AsyncMock())),
        'd': SimpleNamespace(job=Mock(is_started=False, is_finished=True, is_enabled=True, wait=AsyncMock())),
        'e': SimpleNamespace(job=Mock(is_started=True, is_finished=False, is_enabled=False, wait=AsyncMock())),
        'f': SimpleNamespace(job=Mock(is_started=True, is_finished=False, is_enabled=True, wait=AsyncMock())),
        'g': SimpleNamespace(job=Mock(is_started=True, is_finished=True, is_enabled=False, wait=AsyncMock())),
        'h': SimpleNamespace(job=Mock(is_started=True, is_finished=True, is_enabled=True, wait=AsyncMock())),
    }
    mocker.patch.object(ui, '_finish_jobs', Mock())
    await ui._terminate_jobs(callback=callback)
    assert ui._finish_jobs.call_args_list == [call()]
    assert ui._jobs['a'].job.wait.call_args_list == []
    assert ui._jobs['b'].job.wait.call_args_list == []
    assert ui._jobs['c'].job.wait.call_args_list == []
    assert ui._jobs['d'].job.wait.call_args_list == []
    assert ui._jobs['e'].job.wait.call_args_list == []
    assert ui._jobs['f'].job.wait.call_args_list == [call()]
    assert ui._jobs['g'].job.wait.call_args_list == []
    assert ui._jobs['h'].job.wait.call_args_list == []
    if callback:
        assert callback.call_args_list == [call()]


@pytest.mark.asyncio  # Ensure aioloop exists
async def test_finish_jobs():
    ui = TUI()
    ui._jobs = {
        'a': SimpleNamespace(job=Mock(is_finished=False, is_enabled=False)),
        'b': SimpleNamespace(job=Mock(is_finished=True, is_enabled=False)),
        'c': SimpleNamespace(job=Mock(is_finished=False, is_enabled=True)),
        'd': SimpleNamespace(job=Mock(is_finished=True, is_enabled=True)),
    }
    ui._finish_jobs()
    assert ui._jobs['a'].job.finish.call_args_list == []
    assert ui._jobs['b'].job.finish.call_args_list == []
    assert ui._jobs['c'].job.finish.call_args_list == [call()]
    assert ui._jobs['d'].job.finish.call_args_list == []


@pytest.mark.asyncio  # Ensure aioloop exists
async def test_get_exception_from_loop_exception_handler():
    ui = TUI()
    ui._exception = ValueError('asdf')
    ui._jobs = {
        'a': SimpleNamespace(job=Mock(raised=ValueError('foo'), is_enabled=False)),
        'b': SimpleNamespace(job=Mock(raised=None, is_enabled=False)),
        'c': SimpleNamespace(job=Mock(raised=ValueError('bar'), is_enabled=True)),
        'd': SimpleNamespace(job=Mock(raised=None, is_enabled=True)),
    }
    exc = ui._get_exception()
    assert isinstance(exc, ValueError)
    assert str(exc) == 'asdf'

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_get_exception_from_first_failed_enabled_job():
    ui = TUI()
    ui._exception = None
    ui._jobs = {
        'a': SimpleNamespace(job=Mock(raised=ValueError('foo'), is_enabled=False)),
        'b': SimpleNamespace(job=Mock(raised=None, is_enabled=False)),
        'c': SimpleNamespace(job=Mock(raised=ValueError('bar'), is_enabled=True)),
        'd': SimpleNamespace(job=Mock(raised=None, is_enabled=True)),
    }
    exc = ui._get_exception()
    assert isinstance(exc, ValueError)
    assert str(exc) == 'bar'

@pytest.mark.asyncio  # Ensure aioloop exists
async def test_get_exception_returns_None_if_no_exception_raised():
    ui = TUI()
    ui._exception = None
    ui._jobs = {
        'a': SimpleNamespace(job=Mock(raised=None, is_enabled=False)),
        'b': SimpleNamespace(job=Mock(raised=None, is_enabled=False)),
        'c': SimpleNamespace(job=Mock(raised=None, is_enabled=True)),
        'd': SimpleNamespace(job=Mock(raised=None, is_enabled=True)),
    }
    assert ui._get_exception() is None
