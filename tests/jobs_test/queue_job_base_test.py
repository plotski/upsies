import asyncio
import inspect
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies.jobs import JobBase, QueueJobBase


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


class FooJob(QueueJobBase):
    name = 'foo'
    label = 'Foo'

    def initialize(self, foo=None, bar=None, enqueue=()):
        self.handled_inputs = []

    async def _handle_input(self, value):
        self.handled_inputs.append(value)


@pytest.fixture
@pytest.mark.asyncio
async def qjob(tmp_path):
    qjob = FooJob(homedir=tmp_path, ignore_cache=False)
    yield qjob
    if inspect.isawaitable(qjob._read_queue_task):
        qjob.finish()
        await qjob.wait()


def test_QueueJobBase_is_JobBase_subclass(qjob):
    assert isinstance(qjob, JobBase)


def test_enqueue_argument_is_empty(mocker, tmp_path):
    mocker.patch('upsies.jobs.base.QueueJobBase.enqueue')
    mocker.patch('upsies.jobs.base.QueueJobBase.finalize')
    qjob = FooJob(enqueue=(), homedir=tmp_path, ignore_cache=False)
    assert qjob.enqueue.call_args_list == []
    assert qjob.finalize.call_args_list == []

def test_enqueue_argument_is_not_empty(mocker, tmp_path):
    mocks = Mock()
    mocker.patch('upsies.jobs.base.QueueJobBase.enqueue', mocks.enqueue)
    mocker.patch('upsies.jobs.base.QueueJobBase.finalize', mocks.finalize)
    FooJob(enqueue=(1, 2, 3), homedir=tmp_path, ignore_cache=False)
    assert mocks.mock_calls == [
        call.enqueue(1),
        call.enqueue(2),
        call.enqueue(3),
        call.finalize(),
    ]


def test_execute(qjob, mocker):
    mocker.patch('asyncio.ensure_future')
    mocker.patch.object(qjob, '_read_queue', Mock())
    assert qjob._read_queue_task is None
    qjob.execute()
    assert qjob._read_queue.call_args_list == [call()]
    assert asyncio.ensure_future.call_args_list == [call(qjob._read_queue.return_value)]
    assert qjob._read_queue_task == asyncio.ensure_future.return_value


@pytest.mark.asyncio
async def test_read_queue_reads_queue(qjob, mocker):
    mocker.patch.object(qjob, '_handle_input', AsyncMock())
    qjob._queue.put_nowait('a')
    qjob._queue.put_nowait('b')
    qjob._queue.put_nowait(None)
    await qjob._read_queue()
    assert qjob._queue.empty()
    assert qjob._handle_input.call_args_list == [
        call('a'),
        call('b'),
    ]

@pytest.mark.asyncio
async def test_read_queue_complains_if_job_is_finished(mocker, tmp_path):
    mocker.patch('upsies.jobs.base.QueueJobBase.is_finished', PropertyMock(
        side_effect=(False, True, True, True),
    ))
    qjob = FooJob(homedir=tmp_path, ignore_cache=False)
    mocker.patch.object(qjob, '_handle_input', AsyncMock())
    qjob._queue.put_nowait('a')
    qjob._queue.put_nowait('b')
    qjob._queue.put_nowait('c')
    qjob._queue.put_nowait(None)
    with pytest.raises(RuntimeError, match=r'^FooJob is already finished$'):
        await qjob._read_queue()
    assert not qjob._queue.empty()
    assert qjob._handle_input.call_args_list == [call('a')]


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
    qjob.finish()
    assert qjob._read_queue_task is None
    assert not qjob.is_finished

@pytest.mark.asyncio
async def test_finish_with_running_read_queue_task(qjob):
    qjob.execute()
    qjob.finish()
    assert qjob._read_queue_task is not None
    assert not qjob.is_finished


@pytest.mark.asyncio
async def test_wait_without_running_read_queue_task(qjob):
    assert qjob._read_queue_task is None
    assert not qjob.is_finished
    await qjob.wait()
    assert qjob.is_finished
    assert qjob.errors == ()
    assert qjob._read_queue_task is None

@pytest.mark.asyncio
async def test_wait_awaits_read_queue_task(qjob):
    qjob.execute()
    assert qjob._read_queue_task is not None
    assert not qjob.is_finished
    asyncio.get_event_loop().call_soon(qjob.finalize())
    await qjob.wait()
    assert qjob.is_finished
    assert qjob.errors == ()
    assert qjob._read_queue_task is not None

@pytest.mark.asyncio
async def test_wait_handles_CancelledError_from_read_queue_task(qjob):
    qjob.execute()
    assert qjob._read_queue_task is not None
    assert not qjob.is_finished
    qjob._read_queue_task.cancel()
    await qjob.wait()
    assert qjob.is_finished
    assert qjob.exit_code == 1
    assert qjob.errors == ('Cancelled',)
    assert qjob._read_queue_task is not None
