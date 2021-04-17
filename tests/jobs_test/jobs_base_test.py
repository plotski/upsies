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


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


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
    return FooJob(home_directory=tmp_path, cache_directory=tmp_path, ignore_cache=False)


def test_home_directory_property(tmp_path):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    assert job.home_directory == tmp_path

def test_cache_directory_property(tmp_path):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path / 'bar')
    assert job.cache_directory == tmp_path / 'bar'

def test_ignore_cache_property(tmp_path):
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, ignore_cache=False).ignore_cache is False
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, ignore_cache=True).ignore_cache is True
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, ignore_cache='').ignore_cache is False
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, ignore_cache=1).ignore_cache is True

def test_hidden_property(tmp_path):
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, hidden=False).hidden is False
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, hidden=True).hidden is True
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, hidden='').hidden is False
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, hidden=1).hidden is True

def test_autostart_property(tmp_path):
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, autostart=False).autostart is False
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, autostart=True).autostart is True
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, autostart='').autostart is False
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, autostart=1).autostart is True

def test_is_enabled_property(tmp_path):
    condition = Mock()
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path, condition=condition)
    condition.return_value = 0
    assert job.is_enabled is False
    condition.return_value = 'yes'
    assert job.is_enabled is True

def test_kwargs_property(tmp_path):
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, foo='a').kwargs.get('foo') == 'a'
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, foo='a').kwargs.get('bar') is None
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, bar='b').kwargs.get('bar') == 'b'
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, bar='b').kwargs.get('foo') is None
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, foo='a', bar='b').kwargs.get('foo') == 'a'
    assert FooJob(home_directory=tmp_path, cache_directory=tmp_path, foo='a', bar='b').kwargs.get('bar') == 'b'

def test_signal_property(job):
    assert isinstance(job.signal, signal.Signal)
    assert set(job.signal.signals) == {'output', 'info', 'warning', 'error', 'finished'}
    assert set(job.signal.recording) == {'output'}


def test_initialize_is_called_after_object_creation(job):
    assert job.initialize_was_called


def test_callbacks_argument(tmp_path):
    class BarJob(FooJob):
        def initialize(self):
            self.signal.add('greeted')

    cb = Mock()
    job = BarJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        callbacks={
            'output': cb.output,
            'finished': cb.finished,
            'greeted': (cb.hello, cb.hey),
        },
    )
    assert cb.output in job.signal.signals['output']
    assert cb.finished in job.signal.signals['finished']
    assert cb.hello in job.signal.signals['greeted']
    assert cb.hey in job.signal.signals['greeted']


def test_start_sets_is_started_property(job):
    assert job.is_started is False
    job.start()
    assert job.is_started is True

def test_start_is_called_multiple_times(job):
    job.start()
    with pytest.raises(RuntimeError, match=r'^start\(\) was already called$'):
        job.start()

def test_start_reads_cache_from_previous_job(tmp_path):
    class BarJob(FooJob):
        def _read_cache(self):
            return True

    job = BarJob(home_directory=tmp_path, cache_directory=tmp_path)
    job.start()
    assert not hasattr(job, 'execute_was_called')
    assert job.is_finished is True

def test_start_finishes_if_reading_from_cache_fails(tmp_path):
    class BarJob(FooJob):
        def _read_cache(self):
            raise RuntimeError('I found god')

    job = BarJob(home_directory=tmp_path, cache_directory=tmp_path)
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

    job = BarJob(home_directory=tmp_path, cache_directory=tmp_path)
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
        assert cb.call_args_list == [call(job)]

@pytest.mark.asyncio
async def test_finish_writes_cache(job, mocker):
    mocker.patch.object(job, '_write_cache')
    job.start()
    for i in range(3):
        job.finish()
        assert job._write_cache.call_args_list == [call()]

@pytest.mark.asyncio
async def test_finish_cancels_added_tasks(job):
    job._tasks = [
        Mock(done=Mock(return_value=False)),
        Mock(done=Mock(return_value=True)),
        Mock(done=Mock(return_value=False)),
    ]
    job.start()
    for task in job._tasks:
        assert task.done.call_args_list == []
        assert task.cancel.call_args_list == []
    for i in range(3):
        job.finish()
        for task in job._tasks:
            assert task.done.call_args_list == [call()]
        assert job._tasks[0].cancel.call_args_list == [call()]
        assert job._tasks[1].cancel.call_args_list == []
        assert job._tasks[2].cancel.call_args_list == [call()]


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


def test_send_emits_output_signal(job, mocker):
    mocker.patch.object(job.signal, 'emit')
    job.start()
    assert job.signal.emit.call_args_list == []
    job.send('foo')
    assert job.signal.emit.call_args_list == [call('output', 'foo')]
    job.send([1, 2])
    assert job.signal.emit.call_args_list == [call('output', 'foo'), call('output', '[1, 2]')]
    job.send('')
    assert job.signal.emit.call_args_list == [
        call('output', 'foo'),
        call('output', '[1, 2]'),
        call('output', ''),
    ]

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


def test_output(job):
    assert job.output == ()
    job._output = ['foo', 'bar', 'baz']
    assert job.output == ('foo', 'bar', 'baz')


def test_info(job):
    cb = Mock()
    job.signal.register('info', cb)
    assert job.info == ''
    assert cb.call_args_list == []
    job.info = 'foo'
    assert job.info == 'foo'
    assert cb.call_args_list == [call('foo')]


def test_warn(job):
    assert job.warnings == ()
    job.warn('foo')
    assert job.warnings == ('foo',)
    job.warn('bar')
    assert job.warnings == ('foo', 'bar')
    job.finish()
    job.warn('baz')
    assert job.warnings == ('foo', 'bar')

def test_warnings(job):
    assert job.warnings == ()
    job._warnings = ['a', 'b', 'c']
    assert job.warnings == ('a', 'b', 'c')

def test_clear_warnings_on_unfinished_job(job):
    job.clear_warnings()
    assert job.warnings == ()
    job.warn('foo')
    assert job.warnings == ('foo',)
    job.clear_warnings()
    assert job.warnings == ()

def test_clear_warnings_on_finished_job(job):
    job.warn('foo')
    assert job.warnings == ('foo',)
    job.finish()
    job.clear_warnings()
    assert job.warnings == ('foo',)


def test_errors(job):
    assert job.errors == ()
    job._errors = ['foo', 'bar', 'baz']
    assert job.errors == ('foo', 'bar', 'baz')

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
    assert job.signal.emit.call_args_list == [call('error', 'foo'), call('finished', job)]

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
        assert job.raised is None

@pytest.mark.asyncio
async def test_exception_sets_exception_that_is_raised_by_wait(job):
    job.exception(TypeError('Sorry, not my type.'))
    for _ in range(5):
        with pytest.raises(TypeError, match=r'^Sorry, not my type\.$'):
            await job.wait()
            assert type(job.raised) is TypeError
            assert str(job.raised) == 'Sorry, not my type.'

@pytest.mark.asyncio
async def test_exception_finishes_job(job):
    assert not job.is_finished
    job.exception(TypeError('Sorry, not my type.'))
    assert job.is_finished


@pytest.mark.asyncio
async def test_added_task_returns_return_value(job, mocker):
    coro = AsyncMock(return_value='foo')
    job.add_task(coro)
    assert await job._tasks[0] == 'foo'
    assert not job.is_finished
    assert job.raised is None

@pytest.mark.asyncio
async def test_added_task_passes_return_value_to_callback(job, mocker):
    callback = Mock()
    coro = AsyncMock(return_value='foo')
    job.add_task(coro, callback=callback)
    assert await job._tasks[0] == 'foo'
    assert not job.is_finished
    assert job.raised is None
    assert callback.call_args_list == [call('foo')]

@pytest.mark.asyncio
async def test_added_task_catches_exceptions(job, mocker):
    callback = Mock()
    coro = AsyncMock(side_effect=TypeError('foo'))
    job.add_task(coro, callback=callback)
    await job._tasks[0]
    assert job.is_finished
    assert isinstance(job.raised, TypeError)
    assert str(job.raised) == 'foo'
    assert callback.call_args_list == []

@pytest.mark.parametrize('finish_when_done', (False, True))
@pytest.mark.asyncio
async def test_added_task_ignores_CancelledError(finish_when_done, job, mocker):
    callback = Mock()
    coro = AsyncMock(side_effect=asyncio.CancelledError())
    job.add_task(coro, callback=callback, finish_when_done=finish_when_done)
    await job._tasks[0]  # No CancelledError raised
    assert job.is_finished == finish_when_done
    assert job.raised is None
    assert callback.call_args_list == []


@pytest.mark.parametrize('cache_file_value', (None, ''))
def test_write_cache_does_nothing_if_cache_file_property_is_falsy(cache_file_value, tmp_path, mocker):
    class BarJob(FooJob):
        cache_file = cache_file_value

    job = BarJob(home_directory=tmp_path, cache_directory=tmp_path)
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

def test_write_cache_does_nothing_if_job_was_not_executed(job):
    job.error('Bar!')
    job.finish()
    job._write_cache()
    assert not os.path.exists(job.cache_file)

def test_write_cache_writes_signal_emissions(tmp_path, mocker):
    class BarJob(FooJob):
        def execute(self):
            pass

    job = BarJob(home_directory=tmp_path, cache_directory=tmp_path)
    job.send('Foo')
    job.start()
    job.finish()
    mocker.patch.object(type(job.signal), 'emissions', PropertyMock(return_value='emissions mock'))
    job._write_cache()
    serialized_emissions = open(job.cache_file, 'rb').read()
    assert job._deserialize_from_cache(serialized_emissions) == 'emissions mock'

@pytest.mark.parametrize(
    argnames='exception, error',
    argvalues=(
        (OSError('No free space left'), 'No free space left'),
        (OSError(errno.EISDIR, 'Is directory'), 'Is directory'),
    ),
)
def test_write_cache_fails_to_write_cache_file(exception, error, job, mocker):
    open_mock = mocker.patch('upsies.jobs.base.open', side_effect=exception)
    job.start()
    job.finish()
    job._output = ['foo']
    with pytest.raises(RuntimeError, match=(rf'^Unable to write cache '
                                            rf'{re.escape(job.cache_file)}: {error}$')):
        job._write_cache()
    assert open_mock.call_args_list == [call(job.cache_file, 'wb')]

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
        job = BarJob(home_directory=tmp_path, cache_directory=tmp_path)
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
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path, ignore_cache=ignore_cache)
    open_mock = mocker.patch('upsies.jobs.base.open')
    assert job._read_cache() is False
    assert open_mock.call_args_list == []

@pytest.mark.parametrize('cache_file_value', (None, ''))
def test_read_cache_does_nothing_if_cache_file_is_falsy(cache_file_value, tmp_path, mocker):
    class BarJob(FooJob):
        cache_file = cache_file_value

    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
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
    assert open_mock.call_args_list == [call(job.cache_file, 'rb')]

def test_read_cache_replays_signal_emissions(job, mocker):
    open(job.cache_file, 'wb').write(job._serialize_for_cache('emissions mock'))
    replay_mock = mocker.patch.object(type(job.signal), 'replay')
    assert job._read_cache() is True
    assert replay_mock.call_args_list == [call('emissions mock')]


def test_cache_file_when_cache_id_is_None(tmp_path, mocker):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    mocker.patch.object(type(job), 'cache_id', PropertyMock(return_value=None))
    assert job.cache_file is None

@pytest.mark.parametrize('cache_id_value', ('', {}, ()), ids=lambda v: repr(v))
def test_cache_file_when_cache_id_is_falsy(cache_id_value, tmp_path, mocker):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    mocker.patch.object(type(job), 'cache_id', PropertyMock(return_value=cache_id_value))
    assert job.cache_file == str(tmp_path / f'{job.name}.json')

def test_cache_file_when_cache_id_is_too_long(tmp_path, mocker):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    job._max_filename_len = 20
    too_long = ''.join(str(n) for n in range(50))
    mocker.patch.object(type(job), 'cache_id', PropertyMock(return_value=too_long))
    mocker.patch.object(type(job), '_cache_id_as_string', Mock(return_value=too_long))
    assert job.cache_file == str(tmp_path / f'{job.name}.0123…4849.json')

def test_cache_file_when_cache_id_is_not_too_long(tmp_path, mocker):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    mocker.patch.object(type(job), 'cache_id', PropertyMock(return_value='something'))
    assert job.cache_file == str(tmp_path / f'{job.name}.something.json')

def test_cache_file_masks_illegal_characters(tmp_path, mocker):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    mocker.patch.object(type(job), 'cache_id', PropertyMock(return_value='hey you there'))
    mocker.patch('upsies.utils.fs.sanitize_filename', side_effect=lambda path: path.replace(' ', '#'))
    assert job.cache_file == str(tmp_path / f'{job.name}.hey#you#there.json')


def test_cache_id(tmp_path):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    assert job.cache_id == ''


def test_cache_id_as_string_when_cache_id_is_nonstring(mocker, tmp_path):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    assert job._cache_id_as_string(123) == '123'

def test_cache_id_as_string_when_cache_id_is_nonstring_iterable(mocker, tmp_path):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    assert job._cache_id_as_string((1, 2, 3)) == '1,2,3'

@pytest.mark.parametrize('value', (object(), print, lambda: None), ids=lambda v: str(v))
def test_cache_id_as_string_when_cache_id_is_mapping_with_nonstringable_key(value, mocker, tmp_path):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    with pytest.raises(RuntimeError, match=rf'^{re.escape(str(type(value)))} has no string representation$'):
        job._cache_id_as_string({1: 'foo', value: 'bar', 3: 'baz'})

@pytest.mark.parametrize('value', (object(), print, lambda: None), ids=lambda v: str(v))
def test_cache_id_as_string_when_cache_id_is_mapping_with_nonstringable_value(value, mocker, tmp_path):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    with pytest.raises(RuntimeError, match=rf'^{re.escape(str(type(value)))} has no string representation$'):
        job._cache_id_as_string({1: 'foo', 2: value, 3: 'baz'})

@pytest.mark.parametrize('value', (object(), print, lambda: None), ids=lambda v: str(v))
def test_cache_id_as_string_when_cache_id_is_sequence_with_nonstringable_item(value, mocker, tmp_path):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    with pytest.raises(RuntimeError, match=rf'^{re.escape(str(type(value)))} has no string representation$'):
        job._cache_id_as_string((1, value, 3))

def test_cache_id_as_string_normalizes_existing_paths(tmp_path):
    some_dir = tmp_path / 'foo' / 'bar'
    some_path = some_dir / 'baz.txt'
    some_dir.mkdir(parents=True)
    some_path.write_text('some thing')
    abs_path = some_path
    rel_path = some_path.relative_to(tmp_path)
    orig_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        job1 = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
        job2 = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
        assert job1._cache_id_as_string(abs_path) == job2._cache_id_as_string(rel_path)
    finally:
        os.chdir(orig_cwd)

def test_cache_id_as_string_normalizes_multibyte_characters(tmp_path, mocker):
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    mocker.patch.object(type(job), 'cache_id', PropertyMock(return_value='kožušček'))
    assert job.cache_file == str(tmp_path / f'{job.name}.kozuscek.json')
