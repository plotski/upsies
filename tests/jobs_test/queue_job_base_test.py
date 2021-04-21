import asyncio
import inspect
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies.jobs import JobBase, QueueJobBase


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


class FooJob(QueueJobBase):
    name = 'foo'
    label = 'Foo'

    def initialize(self, foo=None, bar=None, enqueue=()):
        self.handled_inputs = []

    async def handle_input(self, value):
        self.handled_inputs.append(value)


@pytest.fixture
@pytest.mark.asyncio
async def qjob(tmp_path):
    qjob = FooJob(home_directory=tmp_path, cache_directory=tmp_path, ignore_cache=False)
    yield qjob
    if inspect.isawaitable(qjob._read_queue_task):
        qjob.finish()
        try:
            await qjob.wait()
        except BaseException:
            pass


def test_QueueJobBase_is_JobBase_subclass(qjob):
    assert isinstance(qjob, JobBase)


def test_enqueue_argument_is_empty(mocker, tmp_path):
    mocker.patch('upsies.jobs.base.QueueJobBase.enqueue')
    mocker.patch('upsies.jobs.base.QueueJobBase.finalize')
    qjob = FooJob(home_directory=tmp_path, cache_directory=tmp_path, enqueue=())
    assert qjob._enqueue_args == ()
    assert qjob.enqueue.call_args_list == []
    assert qjob.finalize.call_args_list == []

def test_enqueue_argument_is_not_empty(mocker, tmp_path):
    mocks = Mock()
    mocker.patch('upsies.jobs.base.QueueJobBase.enqueue', mocks.enqueue)
    mocker.patch('upsies.jobs.base.QueueJobBase.finish', mocks.finish)
    qjob = FooJob(home_directory=tmp_path, cache_directory=tmp_path, enqueue=(1, 2, 3))
    assert qjob._enqueue_args == (1, 2, 3)
    assert mocks.mock_calls == []


def test_execute_with_enqueue_argument(mocker, tmp_path):
    mocks = Mock()
    mocker.patch('upsies.jobs.base.QueueJobBase.enqueue', mocks.enqueue)
    mocker.patch('upsies.jobs.base.QueueJobBase.finalize', mocks.finalize)
    mocker.patch('upsies.jobs.base.QueueJobBase._read_queue', Mock())
    mocker.patch('asyncio.ensure_future')
    qjob = FooJob(home_directory=tmp_path, cache_directory=tmp_path, enqueue=(1, 2, 3))
    assert qjob._read_queue_task is None
    qjob.execute()
    assert qjob._read_queue.call_args_list == [call()]
    assert asyncio.ensure_future.call_args_list == [call(qjob._read_queue.return_value)]
    assert qjob._read_queue_task == asyncio.ensure_future.return_value
    assert mocks.mock_calls == [
        call.enqueue(1),
        call.enqueue(2),
        call.enqueue(3),
        call.finalize(),
    ]

def test_execute_without_enqueue_argument(mocker, tmp_path):
    mocks = Mock()
    mocker.patch('upsies.jobs.base.QueueJobBase.enqueue', mocks.enqueue)
    mocker.patch('upsies.jobs.base.QueueJobBase.finalize', mocks.finalize)
    mocker.patch('upsies.jobs.base.QueueJobBase._read_queue', Mock())
    mocker.patch('asyncio.ensure_future')
    qjob = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    assert qjob._read_queue_task is None
    qjob.execute()
    assert qjob._read_queue.call_args_list == [call()]
    assert asyncio.ensure_future.call_args_list == [call(qjob._read_queue.return_value)]
    assert qjob._read_queue_task == asyncio.ensure_future.return_value
    assert mocks.mock_calls == []


@pytest.mark.asyncio
async def test_read_queue_reads_queue(qjob, mocker):
    mocker.patch.object(qjob, 'handle_input', AsyncMock())
    qjob._queue.put_nowait('a')
    qjob._queue.put_nowait('b')
    qjob._queue.put_nowait(None)
    await qjob._read_queue()
    assert qjob._queue.empty()
    assert qjob.handle_input.call_args_list == [
        call('a'),
        call('b'),
    ]

@pytest.mark.asyncio
async def test_read_queue_breaks_if_job_is_finished(mocker, tmp_path):
    mocker.patch('upsies.jobs.base.QueueJobBase.is_finished', PropertyMock(
        side_effect=(False, True, True, True),
    ))
    qjob = FooJob(home_directory=tmp_path, cache_directory=tmp_path)
    qjob.start()
    mocker.patch.object(qjob, 'handle_input', AsyncMock())
    qjob._queue.put_nowait('a')
    qjob._queue.put_nowait('b')
    qjob._queue.put_nowait('c')
    qjob._queue.put_nowait(None)
    await qjob._read_queue()
    assert qjob.is_finished
    assert not qjob._queue.empty()
    assert qjob.handle_input.call_args_list == [call('a')]

@pytest.mark.asyncio
async def test_read_queue_handles_exception_from_handle_input(qjob, mocker):
    mocker.patch.object(qjob, 'handle_input', AsyncMock(
        side_effect=TypeError('argh'),
    ))
    qjob.start()
    qjob._queue.put_nowait('a')
    await qjob._read_queue()
    assert qjob._queue.empty()
    assert qjob.handle_input.call_args_list == [call('a')]
    with pytest.raises(TypeError, match='^argh$'):
        await qjob.wait()


@pytest.mark.asyncio
async def test_enqueue(qjob):
    assert qjob._queue.empty()
    qjob.enqueue('a')
    qjob.enqueue('b')
    qjob.enqueue('c')
    queued_values = []
    while not qjob._queue.empty():
        queued_values.append(qjob._queue.get_nowait())
    assert queued_values == ['a', 'b', 'c']


@pytest.mark.asyncio
async def test_finalize(qjob):
    assert qjob._queue.empty()
    qjob.finalize()
    queued_values = []
    while not qjob._queue.empty():
        queued_values.append(qjob._queue.get_nowait())
    assert queued_values == [None]


@pytest.mark.asyncio
async def test_finish_without_running_read_queue_task(qjob):
    qjob.start()
    assert not qjob.is_finished
    qjob.finish()
    assert qjob.is_finished

@pytest.mark.asyncio
async def test_finish_with_running_read_queue_task(qjob):
    qjob.start()
    assert not qjob.is_finished
    qjob.finish()
    assert qjob.is_finished


@pytest.mark.asyncio
async def test_wait_without_running_read_queue_task(qjob):
    assert qjob._read_queue_task is None
    assert not qjob.is_finished
    asyncio.get_event_loop().call_soon(qjob.start)
    asyncio.get_event_loop().call_soon(qjob.finish)
    await qjob.wait()
    assert qjob.is_finished
    assert qjob.errors == ()

@pytest.mark.asyncio
async def test_wait_awaits_read_queue_task(qjob):
    qjob.start()
    assert qjob._read_queue_task is not None
    assert not qjob.is_finished
    asyncio.get_event_loop().call_soon(qjob.finalize)
    await qjob.wait()
    assert qjob.is_finished
    assert qjob.errors == ()
    assert qjob._read_queue_task.done()

@pytest.mark.asyncio
async def test_wait_handles_CancelledError_from_read_queue_task(qjob):
    qjob.start()
    assert qjob._read_queue_task is not None
    for i in range(1000):
        qjob.enqueue(i)
    assert not qjob.is_finished
    asyncio.get_event_loop().call_soon(qjob.finish)
    await qjob.wait()
    assert qjob.is_finished
    assert qjob.exit_code == 1
    assert qjob._read_queue_task.done()
