import asyncio
import collections
import os

import pytest

from upsies import errors
from upsies.jobs import JobBase


class FooJob(JobBase):
    name = 'foo'
    label = 'Foo'

    def initialize(self):
        assert self.name == 'foo'
        assert self.label == 'Foo'
        assert os.path.isdir(self.homedir)
        assert self.output == ()
        self.initialize_was_called = True

    def execute(self):
        assert self.name == 'foo'
        assert self.label == 'Foo'
        assert os.path.isdir(self.homedir)
        assert self.output == ()
        self.execute_was_called = True


@pytest.fixture
def job(tmp_path):
    return FooJob(homedir=tmp_path, ignore_cache=False)


abstract_methods = (
    'name', 'label', 'initialize', 'execute'
)

@pytest.mark.parametrize('method', abstract_methods)
def test_abstract_methods(method):
    attrs = {name:lambda self: None for name in abstract_methods}
    del attrs[method]
    cls = type('FooJob', (JobBase,), attrs)
    exp_msg = rf"^Can't instantiate abstract class FooJob with abstract methods {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def test_initialize_is_called_after_object_creation(job):
    assert job.initialize_was_called

def test_start_reads_output_cache_from_previous_job(tmp_path):
    class BarJob(FooJob):
        def read_output_cache(self):
            self._output = ['cached output']

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    job.start()
    assert job.output == ('cached output',)
    assert job.is_finished is True
    assert not hasattr(job, 'execute_was_called')

def test_start_executes_job_if_no_cached_output_is_found(job):
    job.start()
    assert job.execute_was_called is True
    assert job.is_finished is False


@pytest.mark.asyncio
async def test_wait_returns_when_finish_is_called(tmp_path):
    class BarJob(FooJob):
        calls = collections.deque()

        def execute(self):
            asyncio.get_event_loop().call_later(0.1, self.finish)

        def finish(self):
            self.calls.append('finish() called')
            super().finish()

        async def wait(self):
            await super().wait()
            self.calls.append('wait() returned')

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    job.start()
    await job.wait()
    assert list(job.calls) == ['finish() called', 'wait() returned']


@pytest.mark.asyncio
async def test_is_finished(job):
    asyncio.get_event_loop().call_soon(job.finish)
    job.start()
    assert job.is_finished is False
    await job.wait()
    assert job.is_finished is True


def test_send_and_output(job):
    job.start()
    assert job.output == ()
    job.send('foo')
    assert job.output == ('foo',)
    job.send([1, 2])
    assert job.output == ('foo', '[1, 2]')

def test_send_on_finished_job(job):
    job.start()
    job.send('foo')
    job.finish()
    assert job.is_finished is True
    assert job.output == ('foo',)
    with pytest.raises(RuntimeError, match=r'^send\(\) called on finished job$'):
        job.send('bar')
    assert job.output == ('foo',)
    job.send('bar', if_not_finished=True)
    assert job.output == ('foo',)

def test_error_and_errors(job):
    assert job.errors == ()
    job.error('Owie!')
    assert job.errors == ('Owie!',)
    job.error('No likey!')
    assert job.errors == ('Owie!', 'No likey!')

def test_error_on_finished_job(job):
    job.error('foo')
    job.finish()
    assert job.is_finished is True
    assert job.errors == ('foo',)
    with pytest.raises(RuntimeError, match=r'^error\(\) called on finished job$'):
        job.error('bar')
    assert job.errors == ('foo',)
    job.error('bar', if_not_finished=True)
    assert job.errors == ('foo',)


def test_exit_code_is_0_if_output_is_not_empty(job):
    job.send('foo')
    job.finish()
    assert job.output == ('foo',)
    assert job.exit_code == 0

def test_exit_code_is_1_if_output_is_empty(job):
    job.finish()
    assert job.output == ()
    assert job.exit_code == 1

def test_exit_code_is_1_if_errors_were_sent(job):
    job.send('foo')
    job.error('bar')
    job.finish()
    assert job.output == ('foo',)
    assert job.errors == ('bar',)
    assert job.exit_code == 1


def test_cache_filepath_has_correct_parent(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    assert job.cache_filepath == str(tmp_path / '.output' / f'{job.name}.json')

def test_cache_filepath_parent_exists(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    assert os.path.exists(os.path.dirname(job.cache_filepath))

def test_cache_filepath_is_writable(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    with open(job.cache_filepath, 'w') as f:
        f.write('something')
    assert open(job.cache_filepath, 'r').read() == 'something'

def test_cache_filepath_cannot_create_output_directory(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    tmp_path.chmod(0o440)
    try:
        with pytest.raises(errors.PermissionError, match=rf'^{tmp_path / ".output"}: Permission denied$'):
            job.cache_filepath
    finally:
        tmp_path.chmod(0o770)


def test_cache_is_not_written_if_output_is_empty(tmp_path, job):
    assert job.output == ()
    job.write_output_cache()
    assert not os.path.exists(os.path.join(job.homedir, f'{job.name}.json'))

def test_cache_is_written_if_output_is_not_empty(job):
    job.send('foo')
    assert job.output == ('foo',)
    job.finish()
    assert os.path.exists(job.cache_filepath)
    assert open(job.cache_filepath, 'r').read() == '["foo"]\n'


def test_cache_is_read_and_job_is_not_executed(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    open(job.cache_filepath, 'w').write('["foo"]\n')
    job.start()
    assert job.output == ('foo',)
    assert job.is_finished is True
    assert not hasattr(job, 'execute_was_called')

def test_cache_is_not_read_if_cache_filepath_does_not_exist(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    job.start()
    assert job.output == ()
    assert job.is_finished is False
    assert not os.path.exists(job.cache_filepath)
    assert job.execute_was_called

def test_cache_is_not_read_with_ignore_cache_argument(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=True)
    open(job.cache_filepath, 'w').write('["foo"]\n')
    assert os.path.exists(job.cache_filepath)
    job.start()
    assert job.output == ()
    assert job.is_finished is False
    assert job.execute_was_called

@pytest.mark.asyncio
async def test_cache_is_properly_written_when_repeating_command(tmp_path):
    class BarJob(FooJob):
        execute_counter = 0
        read_output_cache_counter = 0

        def execute(self):
            self.execute_counter += 1
            self.send('asdf')
            self.finish()

        def read_output_cache(self):
            self.read_output_cache_counter += 1
            super().read_output_cache()

    for i in range(5):
        job = BarJob(homedir=tmp_path, ignore_cache=False)
        assert job.is_finished is False
        assert job.output == ()
        job.start()
        await job.wait()
        assert job.is_finished is True
        assert job.output == ('asdf',)
        assert job.execute_counter == (1 if i == 0 else 0)
        assert job.read_output_cache_counter == 1
