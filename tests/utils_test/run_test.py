from unittest.mock import call, patch

import pytest

from upsies import errors
from upsies.utils import run


@patch('subprocess.run')
@patch('subprocess.PIPE', 'Mocked PIPE')
def test_run_returns_stdout(run_mock):
    run_mock.return_value.stderr = ''
    run_mock.return_value.stdout = 'process output'
    stdout = run.run(['foo', 'bar', '--baz'])
    assert stdout == 'process output'
    assert run_mock.call_args_list == [call(('foo', 'bar', '--baz'),
                                            shell=False,
                                            encoding='utf-8',
                                            stdout='Mocked PIPE',
                                            stderr='Mocked PIPE')]

@patch('subprocess.run')
@patch('subprocess.PIPE', 'Mocked PIPE')
def test_run_raises_ProcessError_if_command_execution_fails(run_mock):
    run_mock.side_effect = OSError()
    with pytest.raises(errors.DependencyError, match=r'^Missing dependency: foo$'):
        run.run(['foo', 'bar', '--baz'])

@patch('subprocess.run')
@patch('subprocess.PIPE', 'Mocked PIPE')
def test_run_raises_ProcessError_if_stderr_is_truthy(run_mock):
    run_mock.return_value.stderr = 'something went wrong'
    run_mock.return_value.stdout = 'process output'
    with pytest.raises(errors.ProcessError, match=r'^something went wrong$'):
        run.run(('foo', 'bar', '--baz'))

@patch('subprocess.run')
@patch('subprocess.PIPE', 'Mocked PIPE')
def test_run_ignores_stderr_on_request(run_mock):
    run_mock.return_value.stderr = 'something went wrong'
    run_mock.return_value.stdout = 'process output'
    stdout = run.run(('foo', 'bar', '--baz'), ignore_stderr=True)
    assert stdout == 'process output'

@patch('subprocess.run')
@patch('subprocess.PIPE', 'Mocked PIPE')
def test_run_caches_stdout_on_request(run_mock):
    run_mock.return_value.stderr = ''
    run_mock.return_value.stdout = 'process output'
    for _ in range(5):
        assert run.run(['foo', 'bar', '--baz'], cache=True) == 'process output'
        assert run_mock.call_args_list == [call(('foo', 'bar', '--baz'),
                                                shell=False,
                                                encoding='utf-8',
                                                stdout='Mocked PIPE',
                                                stderr='Mocked PIPE')]

@patch('subprocess.run')
@patch('subprocess.PIPE', 'Mocked PIPE')
@patch('subprocess.STDOUT', 'Mocked STDOUT')
def test_run_joins_stdout_and_stderr_on_request(run_mock):
    run_mock.return_value.stdout = 'foo'
    run_mock.return_value.stderr = ''
    run.run(['foo'], join_output=True)
    assert run_mock.call_args_list == [call(('foo',),
                                            shell=False,
                                            encoding='utf-8',
                                            stdout='Mocked PIPE',
                                            stderr='Mocked STDOUT')]
