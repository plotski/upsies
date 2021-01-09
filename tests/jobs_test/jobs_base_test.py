import asyncio
import collections
import errno
import os
import re
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies import errors
from upsies.jobs import JobBase
from upsies.utils import signal


class FooJob(JobBase):
    name = 'foo'
    label = 'Foo'

    def initialize(self, foo=None, bar=None):
        assert self.name == 'foo'
        assert self.label == 'Foo'
        assert self.output == ()
        self.initialize_was_called = True

    def execute(self):
        assert self.name == 'foo'
        assert self.label == 'Foo'
        assert self.output == ()
        self.execute_was_called = True


@pytest.fixture
def job(tmp_path):
    return FooJob(homedir=tmp_path, ignore_cache=False)


def test_homedir_property(tmp_path):
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    assert job.homedir == str(tmp_path)
    assert isinstance(job.homedir, str)

def test_ignore_cache_property(tmp_path):
    assert FooJob(homedir=tmp_path, ignore_cache=False).ignore_cache is False
    assert FooJob(homedir=tmp_path, ignore_cache=True).ignore_cache is True
    assert FooJob(homedir=tmp_path, ignore_cache='').ignore_cache is False
    assert FooJob(homedir=tmp_path, ignore_cache=1).ignore_cache is True

def test_hidden_property(tmp_path):
    assert FooJob(homedir=tmp_path, ignore_cache=False, hidden=False).hidden is False
    assert FooJob(homedir=tmp_path, ignore_cache=False, hidden=True).hidden is True
    assert FooJob(homedir=tmp_path, ignore_cache=False, hidden='').hidden is False
    assert FooJob(homedir=tmp_path, ignore_cache=False, hidden=1).hidden is True

def test_autostart_property(tmp_path):
    assert FooJob(homedir=tmp_path, ignore_cache=False, autostart=False).autostart is False
    assert FooJob(homedir=tmp_path, ignore_cache=False, autostart=True).autostart is True
    assert FooJob(homedir=tmp_path, ignore_cache=False, autostart='').autostart is False
    assert FooJob(homedir=tmp_path, ignore_cache=False, autostart=1).autostart is True

def test_kwargs_property(tmp_path):
    assert FooJob(homedir=tmp_path, ignore_cache=False, foo='a').kwargs.get('foo') == 'a'
    assert FooJob(homedir=tmp_path, ignore_cache=False, foo='a').kwargs.get('bar') is None
    assert FooJob(homedir=tmp_path, ignore_cache=False, bar='b').kwargs.get('bar') == 'b'
    assert FooJob(homedir=tmp_path, ignore_cache=False, bar='b').kwargs.get('foo') is None
    assert FooJob(homedir=tmp_path, ignore_cache=False, foo='a', bar='b').kwargs.get('foo') == 'a'
    assert FooJob(homedir=tmp_path, ignore_cache=False, foo='a', bar='b').kwargs.get('bar') == 'b'

def test_signal_property(job):
    assert isinstance(job.signal, signal.Signal)
    assert set(job.signal.signals) == {'output', 'error', 'finished'}
    assert set(job.signal.recording) == {'output'}


def test_initialize_is_called_after_object_creation(job):
    assert job.initialize_was_called


def test_start_is_called_multiple_times(job):
    job.start()
    with pytest.raises(RuntimeError, match=r'^start\(\) was already called$'):
        job.start()

def test_start_reads_cache_from_previous_job(tmp_path):
    class BarJob(FooJob):
        def _read_cache(self):
            return True

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    job.start()
    assert not hasattr(job, 'execute_was_called')
    assert job.is_finished is True

def test_start_finishes_if_reading_from_cache_fails(tmp_path):
    class BarJob(FooJob):
        def _read_cache(self):
            raise RuntimeError('I found god')

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    with pytest.raises(RuntimeError, match=r'I found god'):
        job.start()
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
async def test_finish_finishes(job):
    assert job.is_finished is False
    job.start()
    assert job.is_finished is False
    job.finish()
    assert job.is_finished is True

@pytest.mark.asyncio
async def test_finish_emits_finished_signal(job):
    job.start()
    cb = Mock()
    job.signal.register('finished', cb)
    for _ in range(3):
        job.finish()
        assert cb.call_args_list == [call()]

@pytest.mark.asyncio
async def test_finish_writes_cache(job, mocker):
    mocker.patch.object(job, '_write_cache')
    job.start()
    for i in range(3):
        job.finish()
        assert job._write_cache.call_args_list == [call()]


@pytest.mark.asyncio
async def test_is_finished(job):
    asyncio.get_event_loop().call_soon(job.finish)
    job.start()
    assert job.is_finished is False
    await job.wait()
    assert job.is_finished is True


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


def test_output(job):
    assert job.output == ()
    job._output = ['foo', 'bar', 'baz']
    assert job.output == ('foo', 'bar', 'baz')


def test_info(job):
    assert job.info == ''


def test_send_emits_output_signal(job, mocker):
    mocker.patch.object(job.signal, 'emit')
    job.start()
    assert job.signal.emit.call_args_list == []
    job.send('foo')
    assert job.signal.emit.call_args_list == [call('output', 'foo')]
    job.send([1, 2])
    assert job.signal.emit.call_args_list == [call('output', 'foo'), call('output', '[1, 2]')]

def test_send_ignores_falsy_values(job, mocker):
    mocker.patch.object(job.signal, 'emit')
    job.start()
    assert job.signal.emit.call_args_list == []
    job.send('')
    assert job.signal.emit.call_args_list == []
    job.send(None)
    assert job.signal.emit.call_args_list == []

def test_send_on_finished_job(job):
    job.start()
    job.send('foo')
    job.finish()
    assert job.output == ('foo',)
    job.send('bar')
    assert job.output == ('foo',)

def test_send_fills_output_property(job, mocker):
    job.start()
    assert job.output == ()
    job.send('foo')
    assert job.output == ('foo',)
    job.send([1, 2])
    assert job.output == ('foo', '[1, 2]')


def test_errors(job):
    assert job.errors == ()
    job._errors = ['foo', 'bar', 'baz']
    assert job.errors == ('foo', 'bar', 'baz')


def test_clear_errors(job):
    job.clear_errors()
    assert job.errors == ()
    job.error('foo')
    assert job.errors == ('foo',)
    job.clear_errors()
    assert job.errors == ()

def test_clear_errors_on_finished_job(job):
    job.error('foo')
    assert job.errors == ('foo',)
    job.finish()
    job.clear_errors()
    assert job.errors == ('foo',)


def test_error_emits_error_signal(job, mocker):
    mocker.patch.object(job.signal, 'emit')
    job.start()
    assert job.signal.emit.call_args_list == []
    job.error('foo')
    assert job.signal.emit.call_args_list == [call('error', 'foo')]
    job.error(errors.ContentError('bar'))
    assert job.signal.emit.call_args_list == [call('error', 'foo'),
                                              call('error', errors.ContentError('bar'))]

def test_error_finishes_job(job, mocker):
    job.start()
    assert not job.is_finished
    job.error('foo', finish=True)
    assert job.is_finished

def test_error_on_finished_job(job, mocker):
    mocker.patch.object(job.signal, 'emit')
    job.start()
    job.error('foo')
    assert job.signal.emit.call_args_list == [call('error', 'foo')]
    job.finish()
    job.error('bar')
    assert job.signal.emit.call_args_list == [call('error', 'foo'), call('finished')]

def test_error_fills_errors_property(job, mocker):
    job.start()
    assert job.errors == ()
    job.error('foo')
    assert job.errors == ('foo',)
    job.error(errors.ContentError('bar'))
    assert job.errors == ('foo', errors.ContentError('bar'))


@pytest.mark.asyncio
async def test_exception_on_finished_job(job):
    job.finish()
    job.exception(TypeError('Sorry, not my type.'))
    assert job.is_finished
    for _ in range(5):
        await job.wait()  # No exception

@pytest.mark.asyncio
async def test_exception_sets_exception_that_is_raised_by_wait(job):
    job.exception(TypeError('Sorry, not my type.'))
    for _ in range(5):
        with pytest.raises(TypeError, match=r'^Sorry, not my type\.$'):
            await job.wait()

@pytest.mark.asyncio
async def test_exception_finishes_job(job):
    assert not job.is_finished
    job.exception(TypeError('Sorry, not my type.'))
    assert job.is_finished


@pytest.mark.parametrize('cache_file_value', (None, ''))
def test_write_cache_does_nothing_if_cache_file_property_is_falsy(cache_file_value, tmp_path, mocker):
    class BarJob(FooJob):
        cache_file = cache_file_value

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    job.send('Foo')
    job.finish()
    open_mock = mocker.patch('upsies.jobs.base.open')
    job._write_cache()
    assert open_mock.call_args_list == []

def test_write_cache_does_nothing_if_output_is_empty(job, mocker):
    job.finish()
    assert job.output == ()
    job._write_cache()
    assert not os.path.exists(job.cache_file)

def test_write_cache_does_nothing_if_exit_code_is_nonzero(job):
    job.error('Bar!')
    job.finish()
    assert job.exit_code != 0
    job._write_cache()
    assert not os.path.exists(job.cache_file)

def test_write_cache_writes_signal_emissions(job, mocker):
    job.send('Foo')
    job.finish()
    mocker.patch.object(type(job.signal), 'emissions', PropertyMock(return_value='emissions mock'))
    job._write_cache()
    assert open(job.cache_file, 'r').read() == '"emissions mock"\n'

@pytest.mark.parametrize(
    argnames='exception, error',
    argvalues=(
        (OSError('No free space left'), 'No free space left'),
        (OSError(errno.EISDIR, 'Is directory'), 'Is directory'),
    ),
)
def test_write_cache_fails_to_write_cache_file(exception, error, job, mocker):
    open_mock = mocker.patch('upsies.jobs.base.open', side_effect=exception)
    job.finish()
    job._output = ['foo']
    with pytest.raises(RuntimeError, match=(rf'^Unable to write cache '
                                            rf'{re.escape(job.cache_file)}: {error}$')):
        job._write_cache()
    assert open_mock.call_args_list == [call(job.cache_file, 'w')]

@pytest.mark.asyncio
async def test_cache_is_properly_written_when_repeating_command(tmp_path):
    class BarJob(FooJob):
        execute_counter = 0
        read_output_cache_counter = 0

        def execute(self):
            self.execute_counter += 1
            self.send('asdf')
            self.finish()

        def _read_cache(self):
            self.read_output_cache_counter += 1
            return super()._read_cache()

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


@pytest.mark.parametrize('ignore_cache', (False, None, 0, ''))
def test_read_cache_does_nothing_if_ignore_cache_is_falsy(ignore_cache, tmp_path, mocker):
    job = FooJob(homedir=tmp_path, ignore_cache=ignore_cache)
    open_mock = mocker.patch('upsies.jobs.base.open')
    assert job._read_cache() is False
    assert open_mock.call_args_list == []

@pytest.mark.parametrize('cache_file_value', (None, ''))
def test_read_cache_does_nothing_if_cache_file_is_falsy(cache_file_value, tmp_path, mocker):
    class BarJob(FooJob):
        cache_file = cache_file_value

    job = FooJob(homedir=tmp_path, ignore_cache=False)
    open_mock = mocker.patch('upsies.jobs.base.open')
    assert job._read_cache() is False
    assert open_mock.call_args_list == []

def test_read_cache_does_nothing_if_cache_file_does_not_exist(job, mocker):
    open_mock = mocker.patch('upsies.jobs.base.open')
    assert job._read_cache() is False
    assert open_mock.call_args_list == []

@pytest.mark.parametrize(
    argnames='exception, error',
    argvalues=(
        (OSError('No such file'), 'No such file'),
        (OSError(errno.EISDIR, 'Is directory'), 'Is directory'),
    ),
)
def test_read_cache_fails_to_read_cache_file(exception, error, job, mocker):
    mocker.patch('os.path.exists', return_value=True)
    open_mock = mocker.patch('upsies.jobs.base.open', side_effect=exception)
    with pytest.raises(RuntimeError, match=rf'^Unable to read cache {job.cache_file}: {error}$'):
        job._read_cache()
    assert open_mock.call_args_list == [call(job.cache_file, 'r')]

def test_read_cache_replays_signal_emissions(job, mocker):
    open(job.cache_file, 'w').write('"emissions mock"\n')
    replay_mock = mocker.patch.object(type(job.signal), 'replay')
    assert job._read_cache() is True
    assert replay_mock.call_args_list == [call('emissions mock')]


def test_cache_directory_with_default_homedir(job, mocker):
    tmpdir_mock = mocker.patch('upsies.utils.fs.tmpdir')
    job = FooJob(ignore_cache=False)
    assert job.cache_directory is tmpdir_mock.return_value

def test_cache_directory_with_custom_homedir(job, mocker, tmp_path):
    tmpdir_mock = mocker.patch('upsies.utils.fs.tmpdir')
    job = FooJob(homedir=tmp_path, ignore_cache=False)
    assert job.cache_directory == os.path.join(tmp_path, '.cache')
    assert os.path.exists(job.cache_directory)
    assert os.path.isdir(job.cache_directory)
    with open(os.path.join(job.cache_directory, 'foo'), 'w') as f:
        f.write('writable')
    assert open(os.path.join(job.cache_directory, 'foo'), 'r').read() == 'writable'


def test_cache_file_when_cache_id_is_None(tmp_path, mocker):
    class BarJob(FooJob):
        cache_id = None

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    assert job.cache_file is None

@pytest.mark.parametrize('cache_id_value', ('', {}, ()))
def test_cache_file_when_cache_id_is_falsy(cache_id_value, tmp_path, mocker):
    class BarJob(FooJob):
        cache_id = cache_id_value

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    assert job.cache_file == str(tmp_path / '.cache' / f'{job.name}.json')

def test_cache_file_when_cache_id_is_nonstring(tmp_path, mocker):
    class BarJob(FooJob):
        cache_id = 123

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    assert job.cache_file == str(tmp_path / '.cache' / f'{job.name}.123.json')

def test_cache_file_when_cache_id_is_iterable(tmp_path, mocker):
    class BarJob(FooJob):
        cache_id = iter((1, 'two', 3))

    job = BarJob(homedir=tmp_path, ignore_cache=False)
    assert job.cache_file == str(tmp_path / '.cache' / f'{job.name}.1,two,3.json')

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

def test_cache_file_name_does_not_contain_illegal_characters(tmp_path, mocker):
    class BarJob(FooJob):
        cache_id = 'hey you there'

    mocker.patch('upsies.utils.fs.sanitize_filename',
                 side_effect=lambda path: path.replace(' ', '#'))
    job = BarJob(homedir=tmp_path, ignore_cache=False)
    assert job.cache_file == str(tmp_path / '.cache' / f'{job.name}.hey#you#there.json')

def test_cache_file_name_is_never_too_long(tmp_path):
    class BarJob(FooJob):
        def initialize(self, **kwargs):
            pass

    job = BarJob(homedir=tmp_path, ignore_cache=False,
                 **{str(i):i for i in range(1000)})
    assert len(os.path.basename(job.cache_file)) < 255


def test_cache_id_includes_keyword_arguments(tmp_path):
    class BarJob(FooJob):
        def initialize(self, foo, bar, baz):
            pass

    kwargs = {'foo': 'asdf', 'bar': (1, 2, 3), 'baz': {'hey': 'ho', 'hoo': ['ha', 'ha', 'ha']}}
    job = BarJob(homedir=tmp_path, ignore_cache=False, **kwargs)
    assert job.cache_id == kwargs

def test_cache_id_complains_about_keyword_arguments_with_no_string_representation(tmp_path):
    class BarJob(FooJob):
        def initialize(self, foo, bar, baz):
            pass

    kwargs = {'foo': 'asdf', 'bar': (1, 2, 3), 'baz': object()}
    job = BarJob(homedir=tmp_path, ignore_cache=False, **kwargs)
    with pytest.raises(RuntimeError, match=r"<class 'object'> has no string representation"):
        job.cache_id
