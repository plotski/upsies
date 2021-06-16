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


@pytest.mark.parametrize(
    argnames='path, exp_exception',
    argvalues=(
        ('path/to/home', None),
        ('', None),
        (None, None),
        ('/root/upsies/test', errors.ContentError('/root/upsies/test: Permission denied')),
    ),
)
def test_home_directory_property(path, exp_exception, tmp_path):
    if path is None:
        job = FooJob()
        assert job.home_directory == ''
    else:
        job = FooJob(home_directory=tmp_path / path)
        if exp_exception:
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
                job.home_directory
        else:
            assert job.home_directory == tmp_path / path
            assert os.path.exists(job.home_directory)


@pytest.mark.parametrize(
    argnames='path',
    argvalues=(
        'path/to/cache',
        '',
        None,
    ),
)
def test_cache_directory_property(path, tmp_path, mocker):
    mocker.patch('upsies.constants.CACHE_DIRPATH', tmp_path / 'cache/path')
    if not path:
        job = FooJob()
        assert job.cache_directory == tmp_path / 'cache/path'
    else:
        job = FooJob(cache_directory=tmp_path / path)
        assert job.cache_directory == tmp_path / path
        assert os.path.exists(job.cache_directory)


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

def test_condition_property(tmp_path):
    a, b = Mock(), Mock()
    job = FooJob(home_directory=tmp_path, cache_directory=tmp_path, condition=a)
    assert job.condition is a
    job.condition = b
    assert job.condition is not a
    assert job.condition is b
    with pytest.raises(TypeError, match=r"Not callable: 'foo'"):
        job.condition = 'foo'

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


def test_start_does_nothing_if_job_is_not_enabled(job):
    job.condition = lambda: False
    assert job.is_enabled is False
    assert job.is_started is False
    job.start()
    assert job.is_started is False

def test_start_sets_started_property(job):
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


@pytest.mark.parametrize(
    argnames='is_started, is_finished, is_enabled, exp_finished',
    argvalues=(
        (True, True, True, False),
        (True, True, False, False),
        (True, False, True, True),
        (False, True, True, False),
        (True, False, False, True),
        (False, False, True, True),
        (False, True, False, False),
        (False, False, False, True),
    ),
)
@pytest.mark.asyncio
async def test_finish(is_started, is_finished, is_enabled, exp_finished, job, mocker):
    mocker.patch.object(type(job), 'is_started', PropertyMock(return_value=is_started))
    mocker.patch.object(type(job), 'is_finished', PropertyMock(return_value=is_finished))
    mocker.patch.object(type(job), 'is_enabled', PropertyMock(return_value=is_enabled))

    cb = Mock()
    job.signal.register('finished', cb)
    mocker.patch.object(job, '_write_cache')
    job._tasks = [
        Mock(done=Mock(return_value=False)),
        Mock(done=Mock(return_value=True)),
        Mock(done=Mock(return_value=False)),
    ]

    job.start()

    for i in range(1):
        job.finish()
        if exp_finished:
            assert cb.call_args_list == [call(job)]

            for task in job._tasks:
                assert task.done.call_args_list == [call()]
            assert job._tasks[0].cancel.call_args_list == [call()]
            assert job._tasks[1].cancel.call_args_list == []
            assert job._tasks[2].cancel.call_args_list == [call()]

            assert job._write_cache.call_args_list == [call()]
        else:
            assert cb.call_args_list == []

            for task in job._tasks:
                assert task.done.call_args_list == []
            assert job._tasks[0].cancel.call_args_list == []
            assert job._tasks[1].cancel.call_args_list == []
            assert job._tasks[2].cancel.call_args_list == []

            assert job._write_cache.call_args_list == []


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
    job.start()
    job.send('foo')
    job.finish()
    assert job.output == ('foo',)
    assert job.exit_code == 0

def test_exit_code_is_1_if_output_is_empty(job):
    job.start()
    job.finish()
    assert job.output == ()
    assert job.exit_code == 1

def test_exit_code_is_1_if_errors_were_sent(job):
    job.start()
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
    job.start()
    assert job.output == ()
    job._output = ['foo', 'bar', 'baz']
    assert job.output == ('foo', 'bar', 'baz')


def test_info(job):
    job.start()
    cb = Mock()
    job.signal.register('info', cb)
    assert job.info == ''
    assert cb.call_args_list == []
    job.info = 'foo'
    assert job.info == 'foo'
    assert cb.call_args_list == [call('foo')]


def test_warn(job):
    job.start()
    assert job.warnings == ()
    job.warn('foo')
    assert job.warnings == ('foo',)
    job.warn('bar')
    assert job.warnings == ('foo', 'bar')
    job.finish()
    job.warn('baz')
    assert job.warnings == ('foo', 'bar')

def test_warnings(job):
    job.start()
    assert job.warnings == ()
    job._warnings = ['a', 'b', 'c']
    assert job.warnings == ('a', 'b', 'c')

def test_clear_warnings_on_unfinished_job(job):
    job.start()
    job.clear_warnings()
    assert job.warnings == ()
    job.warn('foo')
    assert job.warnings == ('foo',)
    job.clear_warnings()
    assert job.warnings == ()

def test_clear_warnings_on_finished_job(job):
    job.start()
    job.warn('foo')
    assert job.warnings == ('foo',)
    job.finish()
    job.clear_warnings()
    assert job.warnings == ('foo',)


def test_errors(job):
    job.start()
    assert job.errors == ()
    job._errors = ['foo', 'bar', 'baz']
    assert job.errors == ('foo', 'bar', 'baz')

@pytest.mark.parametrize('error', ('foo', errors.ContentError('bar')))
def test_error_emits_error_signal(error, job, mocker):
    mocker.patch.object(job.signal, 'emit')
    job.start()
    assert job.signal.emit.call_args_list == []
    job.error(error)
    assert job.signal.emit.call_args_list == [call('error', error), call('finished', job)]

def test_error_finishes_job(job, mocker):
    job.start()
    assert not job.is_finished
    job.error('foo')
    assert job.is_finished

def test_error_on_finished_job(job, mocker):
    mocker.patch.object(job.signal, 'emit')
    job.start()
    assert job.signal.emit.call_args_list == []
    job.finish()
    assert job.signal.emit.call_args_list == [call('finished', job)]
    job.error('foo')
    assert job.signal.emit.call_args_list == [call('finished', job)]

@pytest.mark.parametrize('error', ('foo', errors.ContentError('bar')))
def test_error_appends_to_errors_property(error, job, mocker):
    job.start()
    assert job.errors == ()
    job.error(error)
    assert job.errors == (error,)


@pytest.mark.asyncio
async def test_exception_on_finished_job(job):
    job.start()
    job.finish()
    job.exception(TypeError('Sorry, not my type.'))
    assert job.is_finished
    for _ in range(5):
        await job.wait()  # No exception
        assert job.raised is None

@pytest.mark.asyncio
async def test_exception_sets_exception_that_is_raised_by_wait(job):
    job.start()
    job.exception(TypeError('Sorry, not my type.'))
    for _ in range(5):
        with pytest.raises(TypeError, match=r'^Sorry, not my type\.$'):
            await job.wait()
            assert type(job.raised) is TypeError
            assert str(job.raised) == 'Sorry, not my type.'

@pytest.mark.asyncio
async def test_exception_finishes_job(job):
    job.start()
    assert not job.is_finished
    job.exception(TypeError('Sorry, not my type.'))
    assert job.is_finished


@pytest.mark.asyncio
async def test_added_task_returns_return_value(job, mocker):
    job.start()
    coro = AsyncMock(return_value='foo')
    job.add_task(coro)
    assert await job._tasks[0] == 'foo'
    assert not job.is_finished
    assert job.raised is None

@pytest.mark.asyncio
async def test_added_task_passes_return_value_to_callback(job, mocker):
    job.start()
    callback = Mock()
    coro = AsyncMock(return_value='foo')
    job.add_task(coro, callback=callback)
    assert await job._tasks[0] == 'foo'
    assert not job.is_finished
    assert job.raised is None
    assert callback.call_args_list == [call('foo')]

@pytest.mark.asyncio
async def test_added_task_catches_exceptions(job, mocker):
    job.start()
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
    job.start()
    callback = Mock()
    coro = AsyncMock(side_effect=asyncio.CancelledError())
    job.add_task(coro, callback=callback, finish_when_done=finish_when_done)
    await job._tasks[0]  # No CancelledError raised
    assert job.is_finished == finish_when_done
    assert job.raised is None
    assert callback.call_args_list == []


@pytest.mark.parametrize(
    argnames='emissions, exit_code, cache_file, is_executed',
    argvalues=(
        ((), 0, 'path/to/cache_file', True),
        ((('output', {'args': ('foo',), 'kwargs': {'bar': 'baz'}}),), 1, 'path/to/cache_file', True),
        ((('output', {'args': ('foo',), 'kwargs': {'bar': 'baz'}}),), 0, '', True),
        ((('output', {'args': ('foo',), 'kwargs': {'bar': 'baz'}}),), 0, None, True),
        ((('output', {'args': ('foo',), 'kwargs': {'bar': 'baz'}}),), 1, 'path/to/cache_file', False),
    ),
)
def test_write_cache_does_nothing(emissions, exit_code, cache_file, is_executed, job, mocker):
    mocker.patch.object(type(job.signal), 'emissions', PropertyMock(return_value=emissions))
    mocker.patch.object(type(job), 'exit_code', PropertyMock(return_value=exit_code))
    mocker.patch.object(type(job), 'cache_file', PropertyMock(return_value=cache_file))
    mocker.patch.object(job, '_is_executed', is_executed)
    open_mock = mocker.patch('upsies.jobs.base.open')
    job._write_cache()
    assert open_mock.call_args_list == []

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
    mocker.patch.object(type(job.signal), 'emissions', PropertyMock(return_value='emissions mock'))
    mocker.patch.object(type(job), 'exit_code', PropertyMock(return_value=0))
    mocker.patch.object(type(job), 'cache_file', PropertyMock(return_value='path/to/cache'))
    mocker.patch.object(job, '_is_executed', True)
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


@pytest.mark.parametrize(
    argnames='ignore_cache, cache_file, cache_file_exists',
    argvalues=(
        (True, 'path/to/cache_file', True),
        (1, 'path/to/cache_file', True),
        (False, '', True),
        (False, None, True),
        (1, 'path/to/cache_file', False),
    ),
)
def test_read_cache_does_nothing(ignore_cache, cache_file, cache_file_exists, job, mocker):
    mocker.patch.object(job, '_ignore_cache', ignore_cache)
    mocker.patch.object(type(job), 'cache_file', PropertyMock(return_value=cache_file))
    mocker.patch('os.path.exists', Mock(return_value=cache_file_exists))
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

def test_read_cache_ignores_empty_signal_emission_cache(job, mocker):
    open(job.cache_file, 'wb').write(job._serialize_for_cache(''))
    replay_mock = mocker.patch.object(type(job.signal), 'replay')
    assert job._read_cache() is False
    assert replay_mock.call_args_list == []


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
