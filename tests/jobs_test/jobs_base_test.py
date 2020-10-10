import asyncio
import collections
import os
import re
from unittest.mock import Mock, call, patch

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


@pytest.mark.parametrize('method', JobBase.__abstractmethods__)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in JobBase.__abstractmethods__}
    del attrs[method]
    cls = type('FooJob', (JobBase,), attrs)
    # Python 3.9 changed "methods" to "method"
    exp_msg = rf"^Can't instantiate abstract class FooJob with abstract methods? {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def test_homedir_property(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    assert job.homedir == str(tmp_path)
    assert isinstance(job.homedir, str)

def test_ignore_cache_property(tmp_path):
    assert FooJob(homedir=tmp_path, ignore_cache=False).ignore_cache is False
    assert FooJob(homedir=tmp_path, ignore_cache=True).ignore_cache is True
    assert FooJob(homedir=tmp_path, ignore_cache='').ignore_cache is False
    assert FooJob(homedir=tmp_path, ignore_cache=1).ignore_cache is True

def test_quiet_property(tmp_path):
    assert FooJob(homedir=tmp_path, ignore_cache=False, quiet=False).quiet is False
    assert FooJob(homedir=tmp_path, ignore_cache=False, quiet=True).quiet is True
    assert FooJob(homedir=tmp_path, ignore_cache=False, quiet='').quiet is False
    assert FooJob(homedir=tmp_path, ignore_cache=False, quiet=1).quiet is True


def test_initialize_is_called_after_object_creation(job):
    assert job.initialize_was_called

def test_start_reads_output_cache_from_previous_job(tmp_path):
    class BarJob(FooJob):
        def _read_output_cache(self):
            self._output = ['cached output']

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    job.start()
    assert job.output == ('cached output',)
    assert job.is_finished is True
    assert not hasattr(job, 'execute_was_called')

def test_start_finishes_if_reading_from_cache_fails(tmp_path):
    class BarJob(FooJob):
        def _read_output_cache(self):
            raise RuntimeError('I found god')

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    with pytest.raises(RuntimeError, match=r'I found god'):
        job.start()
    assert job.output == ()
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

def test_send_ignores_falsy_values(job):
    job.start()
    assert job.output == ()
    job.send('')
    assert job.output == ()
    job.send(None)
    assert job.output == ()

def test_send_on_finished_job(job):
    job.start()
    job.send('foo')
    job.finish()
    assert job.is_finished is True
    assert job.output == ('foo',)
    with pytest.raises(RuntimeError, match=r'^send\(\) called on finished job$'):
        job.send('bar')
    assert job.output == ('foo',)

def test_on_output_callback_is_called_when_output_is_sent(job):
    cb = Mock()
    job.on_output(cb)
    job.start()
    assert cb.call_args_list == []
    job.send('foo')
    assert cb.call_args_list == [call('foo')]
    job.send('bar')
    assert cb.call_args_list == [call('foo'), call('bar')]
    job.finish()

def test_on_output_callback_is_called_with_cached_output(tmp_path):
    job1 = FooJob(homedir=tmp_path, ignore_cache=False)
    job1.start()
    job1.send('foo')
    job1.send('bar')
    job1.finish()

    job2 = FooJob(homedir=tmp_path, ignore_cache=False)
    cb = Mock()
    job2.on_output(cb)
    job2.start()
    assert job2.is_finished
    assert cb.call_args_list == [call('foo'), call('bar')]


def test_on_finished_callback_is_called_when_job_finishes(job):
    cb = Mock()
    job.on_finished(cb)
    job.start()
    assert cb.call_args_list == []
    job.send('foo')
    assert cb.call_args_list == []
    job.finish()
    assert cb.call_args_list == [call(job)]

def test_on_finished_callback_is_called_with_cached_output(tmp_path):
    job1 = FooJob(homedir=tmp_path, ignore_cache=False)
    job1.start()
    job1.send('foo')
    job1.finish()

    job2 = FooJob(homedir=tmp_path, ignore_cache=False)
    cb = Mock()
    job2.on_finished(cb)
    job2.start()
    assert job2.is_finished
    assert cb.call_args_list == [call(job2)]


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

def test_on_error_callback(job):
    assert job.errors == ()
    cb = Mock()
    job.on_error(cb)
    job.error('Owie!')
    assert cb.call_args_list == [call('Owie!')]
    job.error((1, 2, 3))
    assert cb.call_args_list == [call('Owie!'), call((1, 2, 3))]


def test_info(job):
    assert job.info == ''


def test_exit_code_is_None_if_job_is_not_finished(job):
    assert job.exit_code is None
    job.start()
    assert job.exit_code is None
    job.finish()
    assert job.exit_code is not None

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


@pytest.mark.asyncio
async def test_exception_without_output(job):
    job.exception(TypeError('Sorry, not my type.'))
    job.finish()
    with pytest.raises(TypeError, match=r'^Sorry, not my type\.$'):
        await job.wait()
    assert job.is_finished
    assert job.output == ()
    assert job.errors == ()
    assert job.exit_code == 1

@pytest.mark.asyncio
async def test_exception_with_output(job):
    job.send('foo')
    job.exception(TypeError('Sorry, not my type.'))
    job.finish()
    with pytest.raises(TypeError, match=r'^Sorry, not my type\.$'):
        await job.wait()
    assert job.is_finished
    assert job.output == ('foo',)
    assert job.errors == ()
    assert job.exit_code == 1

@pytest.mark.asyncio
async def test_exception_with_finished_job(job):
    job.finish()
    with pytest.raises(RuntimeError, match=r'^exception\(\) called on finished job$'):
        job.exception(TypeError('Sorry, not my type.'))

@pytest.mark.asyncio
async def test_exception_finishes(job):
    assert not job.is_finished
    job.exception(TypeError('Sorry, not my type.'))
    assert job.is_finished


def test_cache_file_name_includes_keyword_arguments(tmp_path):
    class BarJob(FooJob):
        def initialize(self, bar, baz):
            pass

    job = BarJob(homedir=tmp_path, ignore_cache=False, bar=1, baz='asdf')
    assert job.cache_file == str(tmp_path / '.output' / f'{job.name}.bar=1,baz=asdf.json')

def test_cache_file_name_does_not_contain_illegal_characters(tmp_path):
    class BarJob(FooJob):
        def initialize(self, baz):
            pass

    job = BarJob(homedir=tmp_path, ignore_cache=False, baz='hey/you')
    assert job.cache_file == str(tmp_path / '.output' / f'{job.name}.baz=hey_you.json')

def test_cache_file_normalizes_existing_paths(tmp_path):
    class BarJob(FooJob):
        def initialize(self, some_path):
            pass

    some_dir = tmp_path / 'foo' / 'bar'
    some_path = some_dir / 'baz.txt'
    some_dir.mkdir(parents=True)
    some_path.write_text('some thing')
    abs_path = some_path
    rel_path = some_path.relative_to(tmp_path)
    orig_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        job1 = BarJob(homedir=tmp_path, ignore_cache=False, some_path=abs_path)
        job2 = BarJob(homedir=tmp_path, ignore_cache=False, some_path=rel_path)
        assert job1.cache_file == job2.cache_file
    finally:
        os.chdir(orig_cwd)

def test_cache_file_has_correct_parent(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    assert job.cache_file == str(tmp_path / '.output' / f'{job.name}.json')

def test_cache_file_parent_directory_exists(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    assert os.path.exists(os.path.dirname(job.cache_file))

def test_cache_file_is_writable(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    with open(job.cache_file, 'w') as f:
        f.write('something')
    assert open(job.cache_file, 'r').read() == 'something'

def test_cache_file_cannot_create_output_directory(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    tmp_path.chmod(0o440)
    try:
        with pytest.raises(errors.PermissionError, match=rf'^{tmp_path / ".output"}: Permission denied$'):
            job.cache_file
    finally:
        tmp_path.chmod(0o770)

def test_cache_file_name_is_never_too_long(tmp_path):
    class BarJob(FooJob):
        def initialize(self, **kwargs):
            pass

    job = BarJob(homedir=tmp_path, ignore_cache=False,
                 **{str(i):i for i in range(1000)})
    assert len(os.path.basename(job.cache_file)) < 255


@pytest.mark.parametrize('cache_file_value', (None, ''))
def test_cache_is_not_written_if_cache_file_property_is_falsy(cache_file_value, tmp_path):
    class BarJob(FooJob):
        cache_file = cache_file_value

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    job.send('Foo')
    job.finish()
    assert job.cache_file is cache_file_value
    with patch('upsies.jobs._base.open') as open_mock:
        job._write_output_cache()
        assert open_mock.call_args_list == []

def test_cache_is_not_written_if_output_is_empty(job):
    assert job.output == ()
    job._write_output_cache()
    assert not os.path.exists(job.cache_file)

def test_cache_is_not_written_if_exit_code_is_nonzero(job):
    job.send('Foo')
    job.error('Bar!')
    job.finish()
    assert job.exit_code != 0
    job._write_output_cache()
    assert not os.path.exists(job.cache_file)

def test_cache_is_written_if_output_is_not_empty(job):
    job.send('foo')
    job.finish()
    assert job.output == ('foo',)
    assert os.path.exists(job.cache_file)
    assert open(job.cache_file, 'r').read() == '["foo"]\n'

@pytest.mark.asyncio
async def test_cache_is_properly_written_when_repeating_command(tmp_path):
    class BarJob(FooJob):
        execute_counter = 0
        read_output_cache_counter = 0

        def execute(self):
            self.execute_counter += 1
            self.send('asdf')
            self.finish()

        def _read_output_cache(self):
            self.read_output_cache_counter += 1
            super()._read_output_cache()

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

def test_writing_cache_that_is_not_JSON_serializable(job):
    job.finish()
    job._output = (object(),)
    # Python 3.6 quotes the type name in the error message
    with pytest.raises(RuntimeError, match=(rf'^Unable to serialize JSON: {re.escape(str(job._output))}: '
                                            'Object of type \'?object\'? is not JSON serializable$')):
        job._write_output_cache()

def test_writing_unwritable_cache_file(tmp_path):
    class BarJob(FooJob):
        @property
        def cache_directory(self):
            return os.path.join('non', 'existing', 'path')
    job = BarJob(homedir=tmp_path, ignore_cache=False)
    job.finish()
    job._output = ['foo']
    with pytest.raises(RuntimeError, match=(rf'^Unable to write cache {re.escape(job.cache_file)}: '
                                            'No such file or directory$')):
        job._write_output_cache()


def test_cache_is_read_and_job_is_not_executed(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    open(job.cache_file, 'w').write('["foo"]\n')
    job.start()
    assert job.output == ('foo',)
    assert job.is_finished is True
    assert not hasattr(job, 'execute_was_called')

def test_cache_is_not_read_if_cache_file_does_not_exist(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    job.start()
    assert job.output == ()
    assert job.is_finished is False
    assert not os.path.exists(job.cache_file)
    assert job.execute_was_called

def test_cache_is_not_read_with_ignore_cache_argument(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=True)
    open(job.cache_file, 'w').write('["foo"]\n')
    assert os.path.exists(job.cache_file)
    job.start()
    assert job.output == ()
    assert job.is_finished is False
    assert job.execute_was_called

@pytest.mark.parametrize('cache_file_value', (None, ''))
def test_cache_is_not_read_if_cache_file_property_is_falsy(cache_file_value, tmp_path):
    class BarJob(FooJob):
        cache_file = cache_file_value

    with patch('upsies.jobs._base.open') as open_mock:
        job = BarJob(homedir=tmp_path, ignore_cache=False)
        assert job.cache_file is cache_file_value
        job.start()
        assert open_mock.call_args_list == []

def test_reading_unreadable_cache_file(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    open(job.cache_file, 'w').write('["foo"]\n')
    os.chmod(job.cache_file, 0o000)
    try:
        with pytest.raises(RuntimeError, match=(rf'^Unable to read cache {re.escape(job.cache_file)}: '
                                                'Permission denied')):
            job._read_output_cache()
    finally:
        os.chmod(job.cache_file, 0o600)
    assert job.output == ()

def test_reading_from_cache_file_with_invalid_JSON(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    open(job.cache_file, 'w').write('[')
    with pytest.raises(RuntimeError, match=(r'^Unable to decode JSON: \'\[\': Expecting ...')):
        job._read_output_cache()
    assert job.output == ()
